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

import _config
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
    except:
    # handling for hardcoding credentials
        NLC_USERNAME = ""
        NLC_PASSWORD = "" 

# location to data is now the same for both local and Bluemix deployment
data_folder = os.path.join(cur_path, 'data')       

ALL_CLASSIFIERS = None

@app.route('/')
def Welcome():
    global CLASSIFIER_READY
    global CLASSIFIER_STATUS
    
    try:
        global NLC_SERVICE
        NLC_SERVICE = NaturalLanguageClassifierV1(
        username=NLC_USERNAME,
        password=NLC_PASSWORD      
        )
    except:
        # catch authentication failures and raise warning message
        NLC_SERVICE = False
        
    if NLC_SERVICE:
        # If the credentials are authenticatted, begin training any instances not initiated and store the UUID/status of each
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
#        classifier_info = json.dumps(CLASSIFIER, indent=4)
        _CLASSIFIER = [{'_name':_name,'_id':data['id'], '_status':data['status']} for _name, data in ALL_CLASSIFIERS.items()]
        classifier_info = ConfigTable(_CLASSIFIER)
        # update the UI, but only the classifier info box
        if CLASSIFIER_READY:
            # fill in the text boxes internally so they don't appear as empty when not used
            return render_template('index.html', classifier_info=classifier_info, classifier_output="", classifier_input = '', error_line = '', test = '', training_icon = "")
        elif CLASSIFIER_STATUS == 'training':
            # Return status on any classifier instances which are still training and a watson work in progress gif
            return render_template('index.html', classifier_info=classifier_info, classifier_output="", classifier_input = '', error_line = 'Classifier is currently %s.' % (CLASSIFIER_STATUS), test = '', training_icon = '<img id="training_icon" src="static/images/ibm-watson.gif" alt=" " class="center"/>')
        else:
            # Return status on any classifier instances which are experiencing issues
            return render_template('index.html', classifier_info=classifier_info, classifier_output="", classifier_input = '', error_line = 'Classifier is currently %s.' % (CLASSIFIER_STATUS), test = '', training_icon = "")
    else:
        # Return only a message that the NLC access has not been provisioned.  Adding credentials to a _config.py file, 
        # hardcoding them in to this script or launching this app through IBM Bluemix will all automate the training process
        return render_template('index.html', classifier_info='', error_line="Please add a _config.py file with your NLC credentials if running locally. "  , classifier_output="", test = '', training_icon = "")
        

@app.route('/classify_text', methods=['GET', 'POST'])
def classify_text():
    # get the text from the UI
    input_text = request.form['classifierinput_text']

    # get info on our classifiers and format their statuses to HTML table
    _CLASSIFIER = [{'_name':_name,'_id':data['id'], '_status':data['status']} for _name, data in ALL_CLASSIFIERS.items()]
    classifier_info = ConfigTable(_CLASSIFIER)

    if CLASSIFIER_READY:
        # check for valid product description
        if input_text != '':
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
            
            # the main objective, a catalogue hierarchy, only using the top choices
            concat_output = '-'.join([_capitalize(i['class_1']) for i in full_output])

            # send results to table formatter
            all_results = ResultsTable(full_output)
            
            # fill in the text boxes internally so they don't appear as empty when not used
            return render_template('index.html', classifier_info=classifier_info, classifier_input = '<textarea rows="5" cols="126"> %s </textarea>' % (input_text), all_results = all_results, error_line = concat_output)
        else:
            # return a reminder that this can only handle product pages from Kohl's if an invalid url is passed
            return render_template('index.html', classifier_info=classifier_info, classifier_input =  '', error_line = 'Invalid Url.  Please provide a product page from Kohls.com, or manually add the product description above.', all_results = '')
    else:
        # return only classifier information in event of failure
        return render_template('index.html', classifier_info=classifier_info, classifier_input = input_text, all_results = '', error_line = 'Classifier is currently %s.' % (CLASSIFIER_STATUS))


        
@app.route('/classify_url', methods=['GET', 'POST'])
def classify_url():
    
    # get info on our classifiers and format their statuses to HTML table
    _CLASSIFIER = [{'_name':_name,'_id':data['id'], '_status':data['status']} for _name, data in ALL_CLASSIFIERS.items()]
    classifier_info = ConfigTable(_CLASSIFIER)
    
    # get the text from the UI    
    input_url = request.form['classifierinput_url']
    
    # send url to parser
    input_text = _get_Kohls_url_info(input_url)

    if CLASSIFIER_READY:
        # check for valid product description
        if input_text:
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
            
            # the main objective, a catalogue hierarchy, only using the top choices
            concat_output = '-'.join([_capitalize(i['class_1']) for i in full_output])

            # send results to table formatter
            all_results = ResultsTable(full_output)
            
            # fill in the text boxes internally so they don't appear as empty when not used
            return render_template('index.html', classifier_info=classifier_info, classifier_input = '<textarea rows="5" cols="126"> %s </textarea>' % (input_text), all_results = all_results, error_line = concat_output)
        else:
            # return a reminder that this can only handle product pages from Kohl's if an invalid url is passed
            return render_template('index.html', classifier_info=classifier_info, classifier_input =  '', error_line = 'Invalid Url.  Please provide a product page from Kohls.com, or manually add the product description above.', all_results = '')
    else:
        # return only classifier information in event of failure
        return render_template('index.html', classifier_info=classifier_info, classifier_input = input_text, all_results = '', error_line = 'Classifier is currently %s.' % (CLASSIFIER_STATUS))
  
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

def _create_classifier():
    # fetch all classifiers associated with the NLC instance
    result = NLC_SERVICE.list_classifiers()
    
    global ALL_CLASSIFIERS
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


def _capitalize(word):
    # formatting for a mistake in assembling the training data
    full_word = []
    for peice in word.split('-'):
        if len(peice) == 1:
            full_word.append(peice.upper())
        else:
            full_word.append(peice[0].upper()+peice[1:].lower())
    return '-'.join(full_word)
        
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
#            desc = ' '.join(desc.split(' ')[:120])
        return desc
    else:
        return False

port = os.getenv('PORT', '5000')
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(port))
