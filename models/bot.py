# from config import Config
from flask import current_app
from google import genai
import os
from google.genai import types

from dotenv import load_dotenv
from PIL import Image
load_dotenv()


class Bot:
    def __init__(self, name, app):
        # self.gm_key = os.environ.get('GEMINI_KEY', None)
        # self.gpt_key = os.environ.get('OPENAI_KEY', None)
        # self.cld_key = os.environ.get('CLAUDE_KEY', None)

        self.gm_key = app.config['SETTINGS']['apiKeys']['gemini']
        self.gpt_key = app.config['SETTINGS']['apiKeys']['openAi']
        self.cld_key = app.config['SETTINGS']['apiKeys']['claude']
        self.active_bot = None
        self.active_bot_name = ""
        self.sys_prompt = f"Your name is {
            name}, you are a general customer service assistant. help the user with the provided data. dont generate information from your own, if you dont know about anything tell the user you can help with that issue please click the request admin button for human help. the attached images are also part of system promtp"
        # self.default_sys_p = self.sys_prompt
        self.bot_maps = {"gm_2.0_f": self._gemini}
        self._set_bot('gm_2.0_f')

    def get_bots(self):
        return ['Gemini 2.0 Flash (gm_2.0_f)']

    # def update_sys_p(self):
    #     os.listdir('')

    def responed(self, input):
        return self.bot_maps[self.active_bot_name](input).text

    def _set_bot(self, name):
        if name == "gm_2.0_f":
            self.active_bot = genai.Client(api_key=self.gm_key)
            self.active_bot_name = name
        else:
            raise NotImplementedError('Not Implemented')

    def _gemini(self, input):
        if self.active_bot_name != 'gm_2.0_f':
            raise ValueError('Select Gemini as active bot before using this')
        else:
            images = []
            text = []
            for file_name in os.listdir(os.path.join(os.getcwd(), 'files')):
                file_ext = os.path.splitext(file_name)[1].lower()
                file_path = os.path.join(os.getcwd(), 'files', file_name)
                # print(file_path)
                if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']:
                    img = Image.open(file_path)
                    images.append(img)
                else:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            text.append(f.read())
                    except:
                        pass
            input_data = [input]
            input_data.extend(images)
            print(input_data)
            response = self.active_bot.models.generate_content(
                model="gemini-2.0-flash", config=types.GenerateContentConfig(system_instruction=self.sys_prompt+".\n\n".join(text), max_output_tokens=1000), contents=input_data)
            return response
            # print(text)
            # print(images)


if __name__ == "__main__":
    b = Bot('test')
    r = b.responed(
        'Hi can you tell me a little about the large package for corporate go hosting? ')
    print(r)
