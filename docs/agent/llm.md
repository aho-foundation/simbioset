
## LLM Model Authorization and Error Handling

This project includes an advanced system for handling Large Language Models (LLMs) with special attention to authorization requirements and error management.

### Authorization for Models Requiring Cookies (e.g., Gemini)

Some LLM models, particularly Google's Gemini models, require authentication through cookies rather than simple API keys. The system handles this automatically:

- **Automatic Detection**: The system automatically detects when a model requires authorization through cookies or other authentication methods
- **Automatic Filtering**: Models that require authentication and don't have proper credentials are automatically excluded from the available model list
- **User Configuration**: Users can optionally configure their own cookies for these models by setting up the appropriate environment variables or configuration files

### Error Handling System

The system distinguishes between temporary and permanent errors on two levels, and **all retries are implemented strictly on the backend side**:

- **Request-level temporary errors**: Network timeouts, connection issues, temporary service unavailability (503, 502, 504 errors) - these trigger retry attempts for the same model
- **Model-level permanent errors**: Authorization failures, invalid API keys, model unavailability, `"model does not exist"` errors (including provider messages like `The model does not exist in https://api.airforce`) - these are considered permanent for the concrete model and the model is removed from rotation
- **Automatic Model Rotation**: When a model fails permanently, it's removed from the available models list and the system automatically retries the request with another available model

This approach ensures that:

- we **do not keep calling a broken model** once the provider says it does not exist or is unauthorized
- all retry and model-rotation logic lives in the backend LLM proxy, there are **no frontend-level retries for LLM calls**
- for the **end user** the error is still treated as *temporary for this request* — the system transparently switches to another model whenever possible instead of exposing raw provider messages or low-level error text in the chat UI (LLM errors are logged only to the server console)
