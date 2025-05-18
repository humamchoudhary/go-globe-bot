import os
import pickle
import base64
from io import BytesIO
from pprint import pprint
from dotenv import load_dotenv
from PIL import Image
import anthropic
import openai
import requests
from google import genai
from google.genai import types

load_dotenv()


class DeepseekClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.deepseek.com/v1/chat/completions"

    def chat(self, messages, temperature=0.7):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": temperature
        }
        response = requests.post(self.base_url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()


class Bot:
    def __init__(self, name, app):
        self.gm_key = app.config['SETTINGS']['apiKeys']['gemini']
        self.gpt_key = app.config['SETTINGS']['apiKeys']['openAi']
        self.cld_key = app.config['SETTINGS']['apiKeys']['claude']
        self.dp_key = app.config['SETTINGS']['apiKeys']['deepseek']
        self.active_bot = None
        self.active_bot_name = ""
        self.sys_prompt = app.config["SETTINGS"]["prompt"]

        self.bot_maps = {
            "gm_2_0_f": self._gemini,
            "claude-3": self._claude,
            "gpt-4": self._gpt,
            "dp-chat": self._deepseek
        }
        self._set_bot('gm_2_0_f')

    def get_bots(self):
        return ['Gemini 2.0 Flash (gm_2_0_f)',
                'Claude 3 (claude-3)',
                'GPT-4 (gpt-4)',
                'Deepseek (dp-chat)']

    def responed(self, input, id):
        if self.active_bot_name not in self.bot_maps:
            raise ValueError(f"Unsupported bot: {self.active_bot_name}")
        return self.bot_maps[self.active_bot_name](input, id)

    def _set_bot(self, name):
        if name == "gm_2_0_f":
            self.active_bot = genai.Client(api_key=self.gm_key)
            self.active_bot_name = name
        elif name == "claude-3":
            self.active_bot = anthropic.Client(api_key=self.cld_key)
            self.active_bot_name = name
        elif name == "gpt-4":
            openai.api_key = self.gpt_key
            self.active_bot_name = name
        elif name == "dp-chat":
            self.active_bot = DeepseekClient(api_key=self.dp_key)
            self.active_bot_name = name
        else:
            raise NotImplementedError('Bot not implemented')

    def create_chat(self, id):
        text_content, images = self._process_files()

        if not os.path.exists('./bin/chat/'):
            os.makedirs('./bin/chat/')

        init_method = getattr(
            self, f'_init_{self.active_bot_name.replace("-", "_")}_chat')
        chat_state = init_method(text_content, images)

        with open(f'bin/chat/{id}.chatpl', 'wb') as file:
            pickle.dump(chat_state, file)

    def _process_files(self):
        text_content = []
        images = []

        if not os.path.exists(os.path.join(os.getcwd(), 'files')):
            return "", []

        for file_name in os.listdir(os.path.join(os.getcwd(), 'files')):
            file_path = os.path.join(os.getcwd(), 'files', file_name)
            file_ext = os.path.splitext(file_name)[1].lower()

            try:
                if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                    with Image.open(file_path) as img:
                        images.append(img.copy())
                elif file_ext == '.txt':
                    url = file_name.replace("*", "/").replace(".txt", "")
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text_content.append(f"<url>{url}</url>")
                        text_content.append(
                            f"<file url='{url}'>{f.read()}</file>")
            except Exception as e:
                print(f"Error processing {file_name}: {str(e)}")

        return "\n".join(text_content), images

    # Bot-specific initializers
    def _init_gm_2_0_f_chat(self, text_content, images):
        history = []
        for img in images:
            buffered = BytesIO()
            img.save(buffered, format="JPEG")
            history.append(types.UserContent(
                types.Part.from_bytes(
                    data=buffered.getvalue(), mime_type='image/jpeg')
            ))

        return {
            "client": self.active_bot,
            "config": {
                "model": "gemini-2.0-flash",
                "config": types.GenerateContentConfig(
                    system_instruction=f"{self.sys_prompt}\n{text_content}",
                    max_output_tokens=500,
                    temperature=0.5
                ),
                "history": history
            }
        }

    def _init_claude_3_chat(self, text_content, images):
        messages = [{
            "role": "system",
            "content": f"{self.sys_prompt}\n{text_content}"
        }]

        for img in images:
            buffered = BytesIO()
            img.save(buffered, format="JPEG")
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": base64.b64encode(buffered.getvalue()).decode('utf-8')
                        }
                    }
                ]
            })

        return {
            "client": self.active_bot,
            "config": {
                "model": "claude-3-opus-20240229",
                "max_tokens": 1000,
                "temperature": 0.7,
                "history": messages
            }
        }

    def _init_gpt_4_chat(self, text_content, images):
        messages = [{
            "role": "system",
            "content": f"{self.sys_prompt}\n{text_content}"
        }]

        for img in images:
            buffered = BytesIO()
            img.save(buffered, format="JPEG")
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": "Attached image:"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64.b64encode(buffered.getvalue()).decode('utf-8')}"
                        }
                    }
                ]
            })

        return {
            "client": openai.ChatCompletion,
            "config": {
                "model": "gpt-4-vision-preview",
                "history": messages
            }
        }

    def _init_dp_chat_chat(self, text_content, images):
        return {
            "client": self.active_bot,
            "config": {
                "model": "deepseek-chat",
                "history": [{
                    "role": "system",
                    "content": f"{self.sys_prompt}\n{text_content}"
                }]
            }
        }

    # Bot response handlers
    def _gemini(self, input, id):
        chat_state = self._load_chat(id)
        response = chat_state["client"].chats.create(
            **chat_state["config"]
        ).send_message(input)

        tokens = self._count_tokens(response)
        self._save_chat(chat_state, id)
        return response.text, tokens

    def _claude(self, input, id):
        chat_state = self._load_chat(id)
        chat_state["config"]["messages"].append(
            {"role": "user", "content": input})

        response = chat_state["client"].messages.create(
            **chat_state["config"]
        )

        tokens = self._count_tokens(response)
        chat_state["config"]["messages"].append({
            "role": "assistant",
            "content": response.content[0].text
        })
        self._save_chat(chat_state, id)
        return response.content[0].text, tokens

    def _gpt(self, input, id):
        chat_state = self._load_chat(id)
        chat_state["config"]["messages"].append(
            {"role": "user", "content": input})

        response = chat_state["client"].create(
            **chat_state["config"]
        )

        tokens = self._count_tokens(response)
        chat_state["config"]["messages"].append({
            "role": "assistant",
            "content": response.choices[0].message.content
        })
        self._save_chat(chat_state, id)
        return response.choices[0].message.content, tokens

    def _deepseek(self, input, id):
        chat_state = self._load_chat(id)
        chat_state["config"]["messages"].append(
            {"role": "user", "content": input})

        response = chat_state["client"].chat(
            **chat_state["config"]
        )

        tokens = self._count_tokens(response)
        chat_state["config"]["messages"].append({
            "role": "assistant",
            "content": response["choices"][0]["message"]["content"]
        })
        self._save_chat(chat_state, id)
        return response["choices"][0]["message"]["content"], tokens

    # Utility methods
    def _load_chat(self, id):
        try:
            with open(f"bin/chat/{id}.chatpl", 'rb') as file:
                return pickle.load(file)
        except FileNotFoundError:
            raise ValueError(f"No chat session found for id {id}")

    def _save_chat(self, chat_state, id):
        with open(f"bin/chat/{id}.chatpl", 'wb') as file:
            pickle.dump(chat_state, file)

    def _count_tokens(self, response):
        pricing = {
            # $ per 1K tokens
            "gm_2_0_f": {"input": 0.000125, "output": 0.000375},
            # $ per 1M tokens
            "claude-3": {"input": 15, "output": 75},
            # $ per 1K tokens
            "gpt-4": {"input": 0.03, "output": 0.06},
            # $ per 1K tokens
            "dp-chat": {"input": 0.0001, "output": 0.0002}
        }

        bot_name = self.active_bot_name
        costs = pricing.get(bot_name, {"input": 0, "output": 0})
        if bot_name == "gm_2_0_f":
            usage = response.usage_metadata.dict()
            input_tokens = usage['prompt_token_count']
            output_tokens = usage['candidates_token_count']
        elif bot_name == "claude-3":
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
        elif bot_name == "gpt-4":
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
        elif bot_name == "dp-chat":
            input_tokens = response["usage"]["prompt_tokens"]
            output_tokens = response["usage"]["completion_tokens"]
        else:
            input_tokens = output_tokens = 0

        # Calculate costs based on pricing model
        if bot_name == "claude-3":
            input_cost = (input_tokens * costs["input"]) / 1000000
            output_cost = (output_tokens * costs["output"]) / 1000000
        else:
            input_cost = (input_tokens * costs["input"]) / 1000
            output_cost = (output_tokens * costs["output"]) / 1000

        return {
            "input": input_tokens,
            "output": output_tokens,
            "cost": input_cost + output_cost,
            "bot": bot_name
        }


if __name__ == "__main__":
    # Example usage
    from flask import Flask
    app = Flask(__name__)
    app.config['SETTINGS'] = {
        'apiKeys': {
            'gemini': os.getenv('GEMINI_API_KEY'),
            'openAi': os.getenv('OPENAI_API_KEY'),
            'claude': os.getenv('CLAUDE_API_KEY'),
            'deepseek': os.getenv('DEEPSEEK_API_KEY')
        },
        'prompt': "You are a helpful AI assistant."
    }

    bot = Bot('test', app)

    # Test each bot
    for bot_name in bot.get_bots():
        print(f"\nTesting {bot_name}...")
        bot._set_bot(bot_name.split(' ')[-1].strip('()'))
        bot.create_chat('test_session')
        response, tokens = bot.responed(
            "Hello! What can you do?", 'test_session')
        print(f"Response: {response[:100]}...")
        print(f"Tokens used: {tokens}")
