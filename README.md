# custom-authorizer-ociiamtoken-caching

OCI Function to cache OCI IAM token in order to access OIC REST Endpoints via API Gateway. This repo is the code for my blog post https://www.ateam-oracle.com/post/use-custom-scopes-to-restrict-access-to-oic-rest-endpoints-with-oci-iam-and-api-gateway

# Running the script
how to run in OCI:

1. Login to OCI Tenancy
2. Create an OCI Function. https://docs.oracle.com/en-us/iaas/Content/Functions/Tasks/functionsuploading.htm 
3. fn init --runtime python CacheToken, then press Enter.
4. Navigate to the function directory, open the func.py file, and seamlessly replace the existing code snippet with the func.py.
5. Include the requirements from the requirements.txt file
6. Navigate to the function folder and run the following command fn -v deploy --app <FunctionApp> to deploy it.
