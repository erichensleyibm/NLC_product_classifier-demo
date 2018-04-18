# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os
import requests
import datetime

# handle no _config.py file added
try:
    import _config
except:
    pass

from flask import Flask, render_template, request
from watson_developer_cloud import NaturalLanguageClassifierV1
from flask_table import Table, Col
from lxml import html

app = Flask(__name__)

# Required classifiers we will need and the data to train them
REQ_CLASSIFIERS = [['Product_description_Top_Level', 'product_descriptions_top_levels_tuncated.csv'],
                   ['Product_description_Gender', 'product_descriptions_gender.csv'],
                   ['Product_description_Health', 'product_descriptions_health.csv'],
                   ['Product_description_Electronics', 'product_descriptions_electronics.csv'],
                   ['Product_description_Home', 'product_descriptions_home.csv'],
                   ['Product_description_Clothing', 'product_descriptions_clothing.csv'],
                   ['Product_description_Apparel', 'product_descriptions_apparel.csv']
                   ]


VCAP_SERVICES = os.getenv("VCAP_SERVICES")
if VCAP_SERVICES is not None:
    # These will be automatically set if deployed to IBM Cloud
    SERVICES = json.loads(VCAP_SERVICES)
    NLC_USERNAME = SERVICES['natural_language_classifier'][0]['credentials']['username']
    NLC_PASSWORD = SERVICES['natural_language_classifier'][0]['credentials']['password']
    # OPTIONAL APP NOTIFICATIONS FROM IBM ALERT NOTIFICATION    
    ALERT_USERNAME = SERVICES['alertnotification'][0]['credentials']['name']
    ALERT_PASSWORD = SERVICES['alertnotification'][0]['credentials']['password']
    # set path when deployed to Bluemix so the same references to other folders can be made as when local
    cur_path = '/home/vcap/app'
else:
    # start with current path
    cur_path = os.path.abspath(__file__)
    # 
    # If you CHANGED the folder name, CHANGE the name here to match,
    # otherwise the while loop will never end
    #
    while cur_path.split('/')[-1] != 'NLC_product_classifier-demo':
        cur_path = os.path.abspath(os.path.join(cur_path, os.pardir))
    try:
    # Set these here for local development
        NLC_USERNAME = _config.NLC_USERNAME
        NLC_PASSWORD = _config.NLC_PASSWORD
        # OPTIONAL APP NOTIFICATIONS FROM IBM ALERT NOTIFICATION
        ALERT_USERNAME = _config.alert_user
        ALERT_PASSWORD = _config.alert_password
    except:
    # handling for hardcoding credentials
        NLC_USERNAME = ""
        NLC_PASSWORD = "" 
        # OPTIONAL APP NOTIFICATIONS FROM IBM ALERT NOTIFICATION
        ALERT_USERNAME = ''
        ALERT_PASSWORD = ''
# location to data is now the same for both local and Bluemix deployment
data_folder = os.path.join(cur_path, 'data')       

# initialize variables
CLASSIFIER_READY = None
CLASSIFIER_STATUS = None
ALL_CLASSIFIERS = None
NLC_SERVICE = None
    
@app.route('/')
def Welcome():
    # call global variables
    global CLASSIFIER_READY
    global CLASSIFIER_STATUS
    global ALL_CLASSIFIERS
    global NLC_SERVICE
    
    try:
        # initiate NLC service
        NLC_SERVICE = NaturalLanguageClassifierV1(
        username=NLC_USERNAME,
        password=NLC_PASSWORD      
        )
    except:
        # catch authentication failures and raise warning message
        NLC_SERVICE = False
        
    if NLC_SERVICE:
        try:
            # If the credentials are authenticated, begin training any instances not initiated and store the UUID/status of each
            ALL_CLASSIFIERS, CLASSIFIER_STATUS, CLASSIFIER_READY = _init_classifiers()
            
            # easier to check no failures than all successes
            if len([data['status'] for data in ALL_CLASSIFIERS.values() if data['status'] in ['Non Existent', 'Training', 'Failed', 'Unavailable']]) == 0:
                # CLASSIFIER_STATUS used both for in app error messages and also can be incorporated into flask_table to trigger HTML formatting
                # by passing the value to flask_table class as an id
                CLASSIFIER_STATUS = 'available'
                CLASSIFIER_READY = True
            elif 'Training' in [data['status'] for data in ALL_CLASSIFIERS.values()]:
                CLASSIFIER_STATUS = 'training'
                CLASSIFIER_READY = False
            else:
                CLASSIFIER_STATUS = 'unavailable'
                CLASSIFIER_READY = False
              
            # retrieve classifier information
            _CLASSIFIER = [{'_name':_name,'_id':data['id'], '_status':data['status']} for _name, data in ALL_CLASSIFIERS.items()]
            classifier_info = ConfigTable(_CLASSIFIER)
            # update the UI, but only the classifier info box
            if CLASSIFIER_READY:
                # fill in the text boxes internally so they don't appear as empty when not used
                return render_template('index.html', classifier_info=classifier_info)
            elif CLASSIFIER_STATUS == 'training':
                # Return status on any classifier instances which are still training
                return render_template('index.html', classifier_info=classifier_info, error_line = 'Classifier is currently %s.' % (CLASSIFIER_STATUS), training_icon = '<img id="training_icon" src="static/images/ibm-watson.gif" alt=" " class="center"/>', scroll_script = '<script src="static/scripts/bottom_scroll.js" language="javascript" type="text/javascript"></script>')
            else:
                # Return status on any classifier instances which are experiencing issues
                return render_template('index.html', classifier_info=classifier_info, error_line = 'Classifier is currently %s.' % (CLASSIFIER_STATUS))
        except Exception as details:
            # send service failure alert            
            _error_alerts(details, Flask(__name__), 'Fatal')
            # return error page
            return render_template('index.html', classifier_info=classifier_info, error_line = 'Unexpected error encountered')
    else:
        # Return only a message that the NLC access has not been provisioned.  Adding credentials to a _config.py file, 
        # hardcoding them in to this script or launching this app through IBM Bluemix will all automate the training process
        return render_template('index.html', error_line="Please add a _config.py file with your NLC credentials if running locally. ", scroll_script = '<script src="static/scripts/bottom_scroll.js" language="javascript" type="text/javascript"></script>')
        

@app.route('/classify_text', methods=['GET', 'POST'])
def classify_text():
    # call global variables
    global CLASSIFIER_READY
    global CLASSIFIER_STATUS
    global ALL_CLASSIFIERS
    global NLC_SERVICE
    
    # get the text from the UI
    input_text = request.form['classifierinput_text']

    # get info on our classifiers and format their statuses to HTML table
    try:
        # retrieve classifier information
        _CLASSIFIER = [{'_name':_name,'_id':data['id'], '_status':data['status']} for _name, data in ALL_CLASSIFIERS.items()]
        classifier_info = ConfigTable(_CLASSIFIER)
    # catch error in retrieving classifier information
    except Exception as details:
        # send service warning alert
        _error_alerts(details, 'classify_text', 'Warning')
        try:
            # rerun retrieval of classifier information
            ALL_CLASSIFIERS, CLASSIFIER_STATUS, CLASSIFIER_READY = _init_classifiers()
            _CLASSIFIER = [{'_name':_name,'_id':data['id'], '_status':data['status']} for _name, data in ALL_CLASSIFIERS.items()]
            classifier_info = ConfigTable(_CLASSIFIER)
        # catch continued error in retreiving classifier information
        except Exception as details_2:
            # send service failure alert
            _error_alerts(details_2, 'classify_text', 'Fatal')
            # return error page
            return render_template('index.html', classifier_info=classifier_info, error_line = 'Unexpected error encountered retrieving NLC instances, please try reloading the home page.', scroll_script = '<script src="static/scripts/bottom_scroll.js" language="javascript" type="text/javascript"></script>')
    
    if CLASSIFIER_READY:
        # check for valid product description
        try:
            if input_text != '': 
                # retrieve classification from text
                full_output = _classify(input_text) 
                
                # the main objective, a catalogue hierarchy, only using the top choices
                concat_output = '-'.join([_capitalize(i['class_1']) for i in full_output])
    
                # send results to table formatter
                all_results = ResultsTable(full_output)
                
                # fill in the text boxes internally so they don't appear as empty when not used
                return render_template('index.html', classifier_info=classifier_info, classifier_input = '<textarea rows="5" cols="126"> %s </textarea>' % (input_text), all_results = all_results, error_line = concat_output, scroll_script = '<script src="static/scripts/bottom_scroll.js" language="javascript" type="text/javascript"></script>')
            else:
                # return a reminder that this can only handle product pages from Kohl's if an invalid url is passed
                return render_template('index.html', classifier_info=classifier_info, error_line = 'Invalid Url.  Please provide a product page from Kohls.com, or manually add the product description above.', scroll_script = '<script src="static/scripts/bottom_scroll.js" language="javascript" type="text/javascript"></script>')
        except Exception as details:
            # send service failure alert
            _error_alerts(details, 'classify_text', 'Fatal')
            # return error page
            return render_template('index.html', classifier_info=classifier_info, error_line = 'Unexpected error encountered', scroll_script = '<script src="static/scripts/bottom_scroll.js" language="javascript" type="text/javascript"></script>')
    else:
        # return only classifier information in event of failure
        return render_template('index.html', classifier_info=classifier_info, classifier_input = input_text, error_line = 'Classifier is currently %s.' % (CLASSIFIER_STATUS), scroll_script = '<script src="static/scripts/bottom_scroll.js" language="javascript" type="text/javascript"></script>')


        
@app.route('/classify_url', methods=['GET', 'POST'])
def classify_url(): 
    global CLASSIFIER_READY
    global CLASSIFIER_STATUS
    global ALL_CLASSIFIERS
    global NLC_SERVICE
    
    # get info on our classifiers and format their statuses to HTML table
    try:
        _CLASSIFIER = [{'_name':_name,'_id':data['id'], '_status':data['status']} for _name, data in ALL_CLASSIFIERS.items()]
        classifier_info = ConfigTable(_CLASSIFIER)
    except Exception as details:
        # send service warning alert
        _error_alerts(details, 'classify_url', 'Warning')
        try:
            # rerun retrieval of classifier information
            ALL_CLASSIFIERS, CLASSIFIER_STATUS, CLASSIFIER_READY = _init_classifiers()
            _CLASSIFIER = [{'_name':_name,'_id':data['id'], '_status':data['status']} for _name, data in ALL_CLASSIFIERS.items()]
            classifier_info = ConfigTable(_CLASSIFIER)
        # catch continued error in retreiving classifier information
        except:
            # send service failure alert
            _error_alerts(details, 'classify_url', 'Fatal')
            # return error page
            return render_template('index.html', classifier_info=classifier_info, error_line = 'Unexpected error encountered retrieving NLC instances, please try reloading the home page.', scroll_script = '<script src="static/scripts/bottom_scroll.js" language="javascript" type="text/javascript"></script>')
    
    # get the text from the UI    
    input_url = request.form['classifierinput_url']
    
    # send url to parser
    input_text = _get_Kohls_url_info(input_url) 
    
    if CLASSIFIER_READY:
        # check for valid product description
        try:
            if input_text:
                # retrieve classification from text
                full_output = _classify(input_text)                
                
                # the main objective, a catalogue hierarchy, only using the top choices
                concat_output = '-'.join([_capitalize(i['class_1']) for i in full_output])
    
                # send results to table formatter
                all_results = ResultsTable(full_output)
                
                # fill in the text boxes internally so they don't appear as empty when not used
                return render_template('index.html', classifier_info=classifier_info, classifier_input = '<textarea rows="5" cols="126"> %s </textarea>' % (input_text), all_results = all_results, error_line = concat_output, scroll_script = '<script src="static/scripts/bottom_scroll.js" language="javascript" type="text/javascript"></script>')
            else:
                # return a reminder that this can only handle product pages from Kohl's if an invalid url is passed
                return render_template('index.html', classifier_info=classifier_info, error_line = 'Invalid Url.  Please provide a product page from Kohls.com, or manually add the product description above.', scroll_script = '<script src="static/scripts/bottom_scroll.js" language="javascript" type="text/javascript"></script>')
        except Exception as details:
            # send service failure alert
            _error_alerts(details, 'classify_url', 'Fatal')
            # return error page
            return render_template('index.html', classifier_info=classifier_info, error_line = 'Unexpected error encountered', scroll_script = '<script src="static/scripts/bottom_scroll.js" language="javascript" type="text/javascript"></script>')
    else:
        # return only classifier information in event of failure
        return render_template('index.html', classifier_info=classifier_info, classifier_input = input_text, error_line = 'Classifier is currently %s.' % (CLASSIFIER_STATUS), scroll_script = '<script src="static/scripts/bottom_scroll.js" language="javascript" type="text/javascript"></script>')
  
class ResultsTable(Table):
    # set class id and table values
    table_id = 'classes'
    class_1 = Col('#1 Choice')
    confidence_1 = Col('#1 Confidence')      
    class_2 = Col('#2 Choice')
    confidence_2 = Col('#2 Confidence') 
                       
class ConfigTable(Table):
    # set class id and table values
    table_id = 'config'
    _name = Col('Name')
    _id = Col('ID') 
    _status = Col('Status') 

def _init_classifiers():
    ALL_CLASSIFIERS = _create_classifier()
    # easier to check no failures than all successes
    if len([data['status'] for data in ALL_CLASSIFIERS.values() if data['status'] in ['Non Existent', 'Training', 'Failed', 'Unavailable']]) == 0:
        # CLASSIFIER_STATUS used both for in app error messages and also can be incorporated into flask_table to trigger HTML formatting
        # by passing the value to flask_table class as an id
        CLASSIFIER_STATUS = 'available'
        CLASSIFIER_READY = True
    elif 'Training' in [data['status'] for data in ALL_CLASSIFIERS.values()]:
        CLASSIFIER_STATUS = 'training'
        CLASSIFIER_READY = False
    else:
        CLASSIFIER_STATUS = 'unavailable'
        CLASSIFIER_READY = False
    return ALL_CLASSIFIERS, CLASSIFIER_STATUS, CLASSIFIER_READY

def _create_classifier():
    # fetch all classifiers associated with the NLC instance
    result = NLC_SERVICE.list_classifiers()    
    ALL_CLASSIFIERS = {}
    
    for name, DATA_SET in REQ_CLASSIFIERS:
        # initiate the dictionary storage for each instance
        ALL_CLASSIFIERS[name] = {'id':'', 'status':''}
        # find any instances which need training but havent been initiated
        if name not in [result['classifiers'][i]['name'] for (i,x) in enumerate(result['classifiers'])]:
            with open(os.path.join(data_folder, DATA_SET), 'rb') as training_data:
                metadata = '{"name": "%s", "language": "en"}' % (name)
                classifier = NLC_SERVICE.create_classifier(
                    metadata=metadata,
                    training_data=training_data
                ) 
                # store classifier information for future handling between the different instances
                ALL_CLASSIFIERS[name]['id'] = classifier['classifier_id'] 
                ALL_CLASSIFIERS[name]['status'] = classifier['status'] 
        else:
            # store classifier information for future handling between the different instances
            ALL_CLASSIFIERS[name]['id'] = [result['classifiers'][i]['classifier_id'] for (i,x) in enumerate(result['classifiers']) if result['classifiers'][i]['name'] == name][0]
            ALL_CLASSIFIERS[name]['status'] = NLC_SERVICE.get_classifier(ALL_CLASSIFIERS[name]['id'])['status']                
    return ALL_CLASSIFIERS

def _classify(input_text):
    # send the text to the first classifier, get high level classification which determines which other classifiers the text is passed to
    classifier_output_0 = NLC_SERVICE.classify(ALL_CLASSIFIERS['Product_description_Top_Level']['id'], input_text)['classes'][:2]
    classifier_output_0 = [{'class_1':classifier_output_0[0]['class_name'], 'confidence_1':classifier_output_0[0]['confidence'], 'class_2':classifier_output_0[1]['class_name'], 'confidence_2':classifier_output_0[1]['confidence']}]
    
    # top level classification of clothing points to this classifier specifically trained on that domain                                   
    if classifier_output_0[0]['class_1'] == 'Apparel-Clothing':
        # initial classification used first determine target gender                                  
        classifier_output_1 = NLC_SERVICE.classify(ALL_CLASSIFIERS['Product_description_Gender']['id'], input_text)['classes'][:2]
        classifier_output_1 = [{'class_1':classifier_output_1[0]['class_name'], 'confidence_1':classifier_output_1[0]['confidence'], 'class_2':classifier_output_1[1]['class_name'], 'confidence_2':classifier_output_1[1]['confidence']}]
        # extra level of classification used first determine product specifics                                  
        classifier_output_2 = NLC_SERVICE.classify(ALL_CLASSIFIERS['Product_description_Clothing']['id'], input_text)['classes'][:2]
        classifier_output_2 = [{'class_1':classifier_output_2[0]['class_name'], 'confidence_1':classifier_output_2[0]['confidence'], 'class_2':classifier_output_2[1]['class_name'], 'confidence_2':classifier_output_2[1]['confidence']}]

    # top level classification of fashion accessories, which are tougher to determine target gender, points to this classifier specifically trained on that domain                                   
    elif classifier_output_0[0]['class_1'] == 'Apparel-Accessories':
        classifier_output_1 = NLC_SERVICE.classify(ALL_CLASSIFIERS['Product_description_Apparel']['id'], input_text)['classes'][:2]
        classifier_output_1 = [{'class_1':classifier_output_1[0]['class_name'], 'confidence_1':classifier_output_1[0]['confidence'], 'class_2':classifier_output_1[1]['class_name'], 'confidence_2':classifier_output_1[1]['confidence']}]
        classifier_output_2 = {}

    # top level classification of electronic and automotive products points to this classifier specifically trained on that domain                       
    elif classifier_output_0[0]['class_1'].split('-')[0] == 'Electronics':
        classifier_output_1 = NLC_SERVICE.classify(ALL_CLASSIFIERS['Product_description_Electronics']['id'], input_text)['classes'][:2]
        classifier_output_1 = [{'class_1':classifier_output_1[0]['class_name'], 'confidence_1':classifier_output_1[0]['confidence'], 'class_2':classifier_output_1[1]['class_name'], 'confidence_2':classifier_output_1[1]['confidence']}]
        classifier_output_2 = {}
        
    # top level classification of health, beauty and fitness products points to this classifier specifically trained on that domain           
    elif classifier_output_0[0]['class_1'].split('_')[0] == 'Health':
        classifier_output_1 = NLC_SERVICE.classify(ALL_CLASSIFIERS['Product_description_Health']['id'], input_text)['classes'][:2]
        classifier_output_1 = [{'class_1':classifier_output_1[0]['class_name'], 'confidence_1':classifier_output_1[0]['confidence'], 'class_2':classifier_output_1[1]['class_name'], 'confidence_2':classifier_output_1[1]['confidence']}]
        classifier_output_2 = {}
    
    # top level classification of home goods points to this classifier specifically trained on that domain
    elif classifier_output_0[0]['class_1'].split('-')[0] == 'Home':
        classifier_output_1 = NLC_SERVICE.classify(ALL_CLASSIFIERS['Product_description_Home']['id'], input_text)['classes'][:2]
        classifier_output_1 = [{'class_1':classifier_output_1[0]['class_name'], 'confidence_1':classifier_output_1[0]['confidence'], 'class_2':classifier_output_1[1]['class_name'], 'confidence_2':classifier_output_1[1]['confidence']}]
        classifier_output_2 = {}
    
    # top two choices for each instance used, along with the corresponding confidence
    full_output = [k[0] for k in [classifier_output_0, classifier_output_1, classifier_output_2] if k != {}]    
    return full_output
                
def _capitalize(word):
    # formatting for a mistake in assembling the training data
    full_word = []
    for peice in word.split('-'):
        if len(peice) == 1:
            full_word.append(peice.upper())
        else:
            full_word.append(peice[0].upper()+peice[1:].lower())
    return '-'.join(full_word)
  
def _error_alerts(details, where, severity):
    global ALERT_USERNAME 
    global ALERT_PASSWORD
    
    # sent failure alert if service in use    
    if ALERT_USERNAME != '' and ALERT_PASSWORD != '':
        message =  "{   \"What\": \"%s\",  \"Where\": \"%s\",  \"Severity\": \"%s\",  \"When\": \"%s\"}"  % (details, where, severity, datetime.datetime.now())
        requests.post("https://ans-us-south.opsmgmt.bluemix.net/api/alerts/v1", auth=(_config.alert_user, _config.alert_password), headers =  {"Content-Type": "application/json", "accept": "application/json"}, data = message)                        
    
def _get_Kohls_url_info(url):
    # parse passed url
    
    # check if valid product description
    if url[8:34] == 'www.kohls.com/product/prd-':
        # extract product_id
        prd_id = url.split('/prd-')[1].split('/')[0]
        raw_desc = []
    
        # loop to handle missed connections
        while raw_desc == []:
            # retrieve page info
            pageContent=requests.get(url)
            # convert to html
            tree = html.fromstring(pageContent.content)
            # parse html using xpath
            raw_desc = tree.xpath('//*[@id="%s_productDetails"]/div/descendant::*/text()' % (prd_id))
            # extract product description
            desc = ' '.join([i for i in raw_desc if i not in ['PRODUCT FEATURES', '\r', '\n']])
            while len(desc.split('  ')) > 1:
                desc = desc.replace('  ', ' ') 
            escapes = ''.join([chr(char) for char in range(1, 32)])
            desc.translate(None, escapes)
            desc = desc[:1000]
            desc = ' '.join(desc.split(' ')[:120])
        return desc
    else:
        return False
    

port = os.getenv('PORT', '5000')
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(port))
