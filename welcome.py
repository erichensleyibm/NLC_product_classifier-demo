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

# The data set we want to use
DATA_SET = 'data/product_description_training.csv'

VCAP_SERVICES = os.getenv("VCAP_SERVICES")
if VCAP_SERVICES is not None:
    # These will be automatically set if deployed to IBM Cloud
    SERVICES = json.loads(VCAP_SERVICES)
    NLC_USERNAME = SERVICES['natural_language_classifier'][0]['credentials']['username']
    NLC_PASSWORD = SERVICES['natural_language_classifier'][0]['credentials']['username']
else:
    try:
    # Set these here for local development
        NLC_USERNAME = _config.NLC_USERNAME
        NLC_PASSWORD = _config.NLC_PASSWORD
    except:
    # handling for hardcoding credentials
        NLC_USERNAME = ""
        NLC_PASSWORD = ""        
    
CLASSIFIER = None

@app.route('/')
def Welcome():
    global CLASSIFIER
    
    try:
        global NLC_SERVICE
        NLC_SERVICE = NaturalLanguageClassifierV1(
        username=NLC_USERNAME,
        password=NLC_PASSWORD      
        )
    except:
        NLC_SERVICE = False
    
    if NLC_SERVICE:
        # create classifier if it doesn't exist, format the json
        CLASSIFIER = _create_classifier()
        classifier_info = json.dumps(CLASSIFIER, indent=4)
        # update the UI, but only the classifier info box
        return render_template('index.html', classifier_info=classifier_info, icd_code="", icd_output="", classifier_output="")
    else:
        return render_template('index.html', classifier_info="Please add a _config.py file with your NLC credentials if running locally. "  , icd_code="", icd_output="", classifier_output="")
        

@app.route('/classify_text', methods=['GET', 'POST'])
def classify_text():
    # get the text from the UI
    input_text = request.form['classifierinput_text']
    # get info about the classifier
    classifier_info = json.dumps(CLASSIFIER, indent=4)

    #check if text is valid
    if input_text != '':
        #send the text to the classifier, get back a product classification
        classifier_output = NLC_SERVICE.classify(CLASSIFIER['classifier_id'], input_text)
        #send results to table formatter
        all_results = ResultsTable(classifier_output['classes'])
        
        return render_template('index.html', classifier_info=classifier_info, classifier_input = input_text, all_results = all_results)
    else:
        return render_template('index.html', classifier_info=classifier_info, classifier_input = 'No description provided.', all_results = '')
        
@app.route('/classify_url', methods=['GET', 'POST'])
def classify_url():
    
    # get info about the classifier
    classifier_info = json.dumps(CLASSIFIER, indent=4)

    # get the text from the UI    
    input_url = request.form['classifierinput_url']
    
    # send url to parser
    input_text = _get_Kohls_url_info(input_url)
    
    # check for valid product description
    if input_text:
        # send the text to the classifier, get back an ICD code
        classifier_output = NLC_SERVICE.classify(CLASSIFIER['classifier_id'], input_text)
        # send results to table formatter
        all_results = ResultsTable(classifier_output['classes'])
        
        # fill in the text boxes
        return render_template('index.html', classifier_info=classifier_info, classifier_input = input_text, all_results = all_results)
    else:
        return render_template('index.html', classifier_info=classifier_info, classifier_input =  'Invalid Url.  Please provide a product page from Kohls.com, or manually add the product description above.', all_results = '')
  
class ResultsTable(Table):
    # set class id and table values
    table_id = 'classes'
    class_name = Col('Class')
    confidence = Col('Confidence')      

def _create_classifier():
    # fetch all classifiers associated with the NLC instance
    result = NLC_SERVICE.list_classifiers()
    # for the purposes of this demo, we handle only one classifier
    # return the first one found
    if len(result['classifiers']) > 0:
        return result['classifiers'][0]
    else:
        # if none found, create a new classifier, change this value
        with open(DATA_SET, 'rb') as training_data:
            metadata = '{"name": "Product_description_classifier", "language": "en"}'
            classifier = NLC_SERVICE.create_classifier(
                metadata=metadata,
                training_data=training_data
            )
        return classifier

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
            desc = ' '.join([i for i in raw_desc if i not in ['PRODUCT FEATURES', '\r']])
        return desc
    else:
        return False

port = os.getenv('PORT', '5000')
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(port))
