# OpenRouterBackroom
## Environment Setup

This project uses environment variables to manage sensitive information like API keys. Follow these steps to set up your environment:

1. Copy the `.env.template` file and rename it to `.env`:
   ```
   cp .env.template .env
   ```

2. Open the `.env` file and replace `your_api_key_here` with your actual OpenRouter API key:
   ```
   OPENROUTER_API_KEY=your_actual_api_key
   ```

3. Do not commit your `.env` file to the repository. It's already included in `.gitignore` to prevent accidental commits.