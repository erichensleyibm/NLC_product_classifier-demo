> **DISCLAIMER**: This application is used for demonstrative and illustrative purposes only. There is no representation as to the accuracy of the output of this application and it is presented without warranty.

# [Demo Web Application](https://erichensley-nlc-demo.mybluemix.net/)

Click on the link above to try out the sample app for yourself! Note, the application is made to classify product descriptions based on the input data.

This app was also featured in an [article](https://medium.com/ibm-watson/e-commerce-product-categorization-with-watson-cf2130d7c94a) on Medium.com which explains the process used and potential business applications.

# Classify E-Commerce product descriptions

This application was built to demonstrate IBM's Watson Natural Language Classifier (NLC). The data set we will be using consists of a cleaned [flipkart](https://www.kaggle.com/PromptCloudHQ/flipkart-products) and [JCPenny](https://www.kaggle.com/PromptCloudHQ/all-jc-penny-products/data) datasets made available through [Kaggle](https://www.kaggle.com). The dataset contains product descriptions and category labels. 

One of the biggest advantages of stores operating online rather than as a brick-and-mortar has been the efficiency of removing physical inventory and labor. Utilizing Watson Natural Language Classifier allows an online marketplace to further optimize their inventory management and cataloging system by classifying products based on their description. Similar to brick-and-mortar stores, e-commerce retailers need to display their products in the correct section of their stores to optimize their user experience. Watson's Natural Language Classification API allows this to be done both at high levels of confidence and on a continual basis.

For demonstration purposes, the app accepts both raw text descriptions as well as product URLs offered by [Kohl's](https://www.kohls.com/), the application extracts the product description and sends it through Watson. [Kohl's](https://www.kohls.com/) was chosen because the nature of products are similar to products on [Flipkart](https://www.flipkart.com/) and [JCPenny](https://www.jcpenney.com/), which were used in training. Although the products themselves are similar, there are many nuanced differences in word choice and usage. Watson's ability to understand and analyze the meanings of words, as opposed to simply memorizing them, is what sets its capabilities apart from other machine learning tools.

This application is a Python web application based on the [Flask microframework](http://flask.pocoo.org/). It uses the [Watson Python SDK](https://github.com/watson-developer-cloud/python-sdk) to create the classifier, list classifiers, and classify the input text. 

[![Deploy to Bluemix](https://bluemix.net/deploy/button.png)](https://bluemix.net/devops/setup/deploy?repository=https://github.com/erichensleyibm/NLC_product_classifier-demo)

## Setup the classifier

Lets get started! Along with these instructions, a [video tutorial](https://www.youtube.com/watch?v=JPMZxgpc_Uo) is also available.

Here we create the classifier with our product description dataset.

1. Download the [product description training dataset](https://github.com/erichensleyibm/NLC_product_classifier-demo/tree/master/data) by right clicking the link and selecting _Save As_.
1. Create an [NLC service in IBM Cloud](https://console.bluemix.net/catalog/services/natural-language-classifier), make a note of the service name used in the catalog, we'll need this later.
1. Create service credentials by using the menu on the left and selecting the default options.
1. Upload the data using the command below. Be sure to substitute the username and password. This will take some time.

```bash
curl -i -u {username}:{password} -F training_data=@data/hierarchy_product_description_training.csv -F training_metadata="{\"language\":\"en\",\"name\":\"hierarchy_product_description_training\"}" "https://gateway.watsonplatform.net/natural-language-classifier/api/v1/classifiers"
```

## Running the application

This application can be run locally or hosted on IBM Cloud, follow the steps below depending on your deployment choice

### Run locally

1. Clone this project: `git clone git@github.com:erichensleyibm/NLC_product_classifier-demo.git`
1. `cd` into this project's root directory
1. (Optionally) create a virtual environment: `virtualenv my-nlc-demo`
    1. Activate the virtual environment: `./my-nlc-demo/bin/activate`
1. Run `pip install -r requirements.txt` to install the app's dependencies
1. Add your NLC credentials
    1. Update the [welcome.py](welcome.py) with your NLC credentials hardcoded
    1. OR add a file named _config.py with your credentials within the same folder as [welcome.py](welcome.py) 
1. Run `python welcome.py`
1. Access the running app in a browser at `http://localhost:5000`

### Run on IBM Cloud

1. Clone this project: `git clone git@github.com:erichensleyibm/NLC_product_classifier-demo.git`
1. `cd` into this project's root directory
1. Update [`manifest.yml`](manifest.yml) with the NLC service name (`your_nlc_service_name`), a unique application name (`your_app_name`) and unique host value (`your_app_host`)

    ```
    applications:
      - path: .
      memory: 256M
      instances: 1
      domain: mybluemix.net
      name: your_app_name
      host: your_app_host
      disk_quota: 1024M
      services:
      - your_nlc_service_name
      buildpack: python_buildpack
    ```

1. Run `bluemix login` from the root directory
1. Run `bluemix target -o <organization> -s <space>`
    1. IBM or other employees using a federated login will need to use `bluemix login --sso` and supply the temporary password provided through following the link given
1. Run `bluemix app push`
1. Access the running app by going to: `https://<host-value>.mybluemix.net/`

> If you've never run the `bluemix` command before there is some configuration required, refer to the official [IBM Cloud CLI](https://console.bluemix.net/docs/cli/reference/bluemix_cli/get_started.html) docs to get this set up.

# Links
* [New Product Announcements](https://medium.com/ibm-watson/you-asked-we-listened-watson-natural-language-classifier-announcements-eef5be222141)
* [Natural Language Classifier API Reference](https://www.ibm.com/watson/developercloud/natural-language-classifier/api/v1/)
* [Watson Python SDK](https://github.com/watson-developer-cloud/python-sdk)
* [IBM Cloud CLI](https://console.bluemix.net/docs/cli/reference/bluemix_cli/get_started.html)
* [Watson Natural Language Classifier](https://www.ibm.com/watson/services/natural-language-classifier/)

# License

[Apache 2.0](LICENSE)
