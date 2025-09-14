from autogen_ext.models.openai import AzureOpenAIChatCompletionClient

az_model_client = AzureOpenAIChatCompletionClient(
    azure_deployment="gpt-5",
    model="gpt-5",
    api_version="2025-02-01-preview",
    azure_endpoint="your-endpoint",
    # azure_ad_token_provider=token_provider,  # Optional if you choose key-based authentication.
    api_key="your-api-key", # For key-based authentication.
)
