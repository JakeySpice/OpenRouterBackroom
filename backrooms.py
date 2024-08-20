import os
from dotenv import load_dotenv
import requests
import json
import time
import re
from datetime import datetime
import sys
import msvcrt
from collections import defaultdict
import signal
import threading

# Load environment variables from .env file
load_dotenv()

# Get the API key from the .env file
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("Please set the OPENROUTER_API_KEY in your .env file")

# Global flag to indicate if the script should exit
should_exit = False

def signal_handler(sig, frame):
    global should_exit
    should_exit = True
    print("\nCtrl+C pressed. Exiting gracefully...")

def escape_chars(text):
    return re.sub(r'\\n', '\n', text)

def read_single_keypress():
    key = msvcrt.getch()
    return key.decode()

def fetch_openrouter_models():
    url = "https://openrouter.ai/api/v1/models"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        return None

def group_models_by_provider(models_data):
    if not models_data:
        return None

    providers = defaultdict(list)
    for model in models_data['data']:
        provider = model['name'].split(':')[0].strip() if ':' in model['name'] else "Other"
        providers[provider].append(model)
    
    return dict(providers)

def display_providers(grouped_models):
    print("\nAvailable Model Providers:")
    print("---------------------------")
    for i, provider in enumerate(grouped_models.keys(), 1):
        print(f"{i}. {provider}")

def display_models_for_provider(provider, models):
    print(f"\nModels available from {provider}:")
    print("---------------------------")
    for i, model in enumerate(models, 1):
        print(f"{i}. {model['name']}")

def select_model(grouped_models, selection_number):
    while True:
        display_providers(grouped_models)
        provider_choice = input(f"\nEnter the number of the provider for Model {selection_number}: ")
        
        try:
            provider_choice = int(provider_choice)
            if 1 <= provider_choice <= len(grouped_models):
                provider = list(grouped_models.keys())[provider_choice - 1]
                display_models_for_provider(provider, grouped_models[provider])
                
                model_choice = input(f"\nEnter the number of the model for Model {selection_number}: ")
                try:
                    model_choice = int(model_choice)
                    if 1 <= model_choice <= len(grouped_models[provider]):
                        return grouped_models[provider][model_choice - 1]
                    else:
                        print("Invalid model choice. Please try again.")
                except ValueError:
                    print("Invalid input. Please enter a number.")
            else:
                print("Invalid provider choice. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def send_openrouter_request(messages, model_id, system_message=None):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model_id,
        "messages": messages
    }
    
    if system_message:
        payload["messages"].insert(0, {"role": "system", "content": system_message})

    try:
        with requests.post(url, headers=headers, json=payload, stream=True) as response:
            response.raise_for_status()
            content = ""
            for chunk in response.iter_content(chunk_size=1024):
                if should_exit:
                    return "Interrupted by user"
                if chunk:
                    content += chunk.decode('utf-8')
            
            response_json = json.loads(content)
        
        if 'choices' in response_json and len(response_json['choices']) > 0:
            return response_json['choices'][0]['message']['content']
        else:
            print(f"Unexpected response structure: {response_json}")
            return "Error: Unexpected response structure"
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        return f"Error: API request failed - {e}"

def converse_with_models(conversation_model1, conversation_model2, model1, model2, num_exchanges=5, supervised_mode=True):
    global should_exit
    timestamp = int(datetime.now().timestamp())
    filename = f"conversation_{timestamp}.txt"

    with open(filename, "w", encoding="utf-8") as file:
        for message in conversation_model1:
            file.write(f"<{message['role'].capitalize()}>\n{escape_chars(message['content'])}\n\n")

        for i in range(num_exchanges):
            if should_exit:
                print("\nExiting due to user interrupt...")
                break

            print(f"\nExchange {i+1}/{num_exchanges}")
            print(f"\n{model1['name']} preparing its message, please wait...\n")
            
            while True:
                response_model1 = send_openrouter_request(conversation_model1, model1['id'])
                if should_exit:
                    break
                formatted_response_model1 = escape_chars(response_model1)
                print(f"{model1['name']}:\n{formatted_response_model1}\n")
                file.write(f"<{model1['name']}>\n{formatted_response_model1}\n\n")

                if supervised_mode:
                    print("Press 'R' to retry the generation or press 'Enter/Return' to submit.")
                    key = read_single_keypress()
                    if key.lower() != 'r':
                        break
                else:
                    break

            if should_exit:
                break

            conversation_model1.append({"role": "assistant", "content": response_model1})
            conversation_model2.append({"role": "user", "content": response_model1})

            time.sleep(2)
            print(f"\n{model2['name']} preparing its message, please wait..\n")
            
            while True:
                response_model2 = send_openrouter_request(conversation_model2, model2['id'])
                if should_exit:
                    break
                formatted_response_model2 = escape_chars(response_model2)
                print(f"{model2['name']}:\n{formatted_response_model2}\n")
                file.write(f"<{model2['name']}>\n{formatted_response_model2}\n\n")

                if supervised_mode:
                    print("Press 'R' to retry the generation or press 'Enter/Return' to continue.")
                    key = read_single_keypress()
                    if key.lower() != 'r':
                        break
                else:
                    break

            if should_exit:
                break

            conversation_model1.append({"role": "user", "content": response_model2})
            conversation_model2.append({"role": "assistant", "content": response_model2})

            time.sleep(2)

    print(f"\nConversation saved to {filename}")

def get_seed_conversation_starter():
    print("\nPlease enter a seed conversation starter:")
    return input().strip()

def main():
    global should_exit
    # Set up the signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    print("Welcome to the OpenRouter Model Selector and Conversation Script!")
    print("Press Ctrl+C at any time to exit the program.")
    
    models = fetch_openrouter_models()
    if not models:
        print("Failed to fetch models.")
        return

    grouped_models = group_models_by_provider(models)
    if not grouped_models:
        print("Failed to group models by provider.")
        return

    model1 = select_model(grouped_models, 1)
    print(f"\nModel 1 selected: {model1['name']}")
    
    model2 = select_model(grouped_models, 2)
    print(f"\nModel 2 selected: {model2['name']}")
    
    print("\nYour selected models:")
    print(f"1. {model1['name']}")
    print(f"2. {model2['name']}")

    # Get seed conversation starter from the user
    seed_starter = get_seed_conversation_starter()

    # Initialize conversations with the seed starter
    conversation_model1 = [
        {"role": "user", "content": seed_starter}
    ]
    conversation_model2 = []

    # Start the conversation
    converse_with_models(conversation_model1, conversation_model2, model1, model2, num_exchanges=5)

if __name__ == "__main__":
    main()