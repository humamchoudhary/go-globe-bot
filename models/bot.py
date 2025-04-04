# from config import Config
from flask import current_app
from google import genai
import os
from google.genai import types
from pprint import pprint
from dotenv import load_dotenv
from PIL import Image
import pickle
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
            name}, you are a general customer service assistant. help the user with the provided data. dont generate information from your own neither give user response that is not related to the content provided, if you dont know about anything tell the user you cant help with that issue please click the request admin button for human help. the attached images are also part of system promtp, also add links to the related file/page at the end where necessary link will be the filename replacing * with / without .txt"
        # self.default_sys_p = self.sys_prompt
        self.bot_maps = {"gm_2.0_f": self._gemini}
        self._set_bot('gm_2.0_f')

    def get_bots(self):
        return ['Gemini 2.0 Flash (gm_2.0_f)']

    # def update_sys_p(self):
    #     os.listdir('')

    def responed(self, input, id):

        res, t = self.bot_maps[self.active_bot_name](input, id)
        return res.text, t

    def _set_bot(self, name):
        if name == "gm_2.0_f":
            genai
            self.active_bot = genai.Client(api_key=self.gm_key)
            self.active_bot_name = name
        else:
            raise NotImplementedError('Not Implemented')

    def create_chat(self, id):
        images = []
        text = []
        history = []
        # history = [types.ModelContent(msg.content) if msg.sender ==
        #            'bot' else types.UserContent(msg.sender) for msg in prev[1:]]
        for file_name in os.listdir(os.path.join(os.getcwd(), 'files')):
            file_ext = os.path.splitext(file_name)[1].lower()
            file_path = os.path.join(os.getcwd(), 'files', file_name)
            # print(file_path)
            if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']:
                img = Image.open(file_path)
                history.append(types.UserContent(
                    types.Part.from_bytes(data=img.tobytes(), mime_type='image/jpg')))
                # images.append(img)
            else:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text.append(file_name)
                        print(file_name)
                        text.append(f.read())
                except:
                    pass
        if not os.path.exists('./bin/chat/'):
            os.makedirs('./bin/chat/')
        with open(f'bin/chat/{id}.chatpl', 'wb') as file:

            chat = self.active_bot.chats.create(
                model="gemini-2.0-flash", config=types.GenerateContentConfig(
                    system_instruction=self.sys_prompt
                    + ".\n\n".join(text),
                    max_output_tokens=1000), history=history)
            pickle.dump(chat, file)

    def _load_chat(self, id):
        with open(f"bin/chat/{id}.chatpl", 'rb') as file:
            chat = pickle.load(file)
        return chat

    def _save_chat(self, chat, id):

        with open(f"bin/chat/{id}.chatpl", 'wb') as file:
            pickle.dump(chat, file)

    def _gemini(self, input, id):
        if self.active_bot_name != 'gm_2.0_f':
            raise ValueError('Select Gemini as active bot before using this')
        else:
            # input_data = [input]
            # input_data.extend(images)
            # print(input_data)
            # print([str(m) for m in prev])
            # response = self.active_bot.models.generate_content(
            #     model="gemini-2.0-flash", config=types.GenerateContentConfig(system_instruction=self.sys_prompt
            #                                                                  + ".\n\n".join(text),
            #                                                                  max_output_tokens=1000), contents=input_data)

            # history.extend(images)
            # types.ModelContent
            # types.UserContent
            # print(prev)
            # print(history)
            chat = self._load_chat(id)
            response = chat.send_message(input)
            # print(chat.get_history())

            # print(self.active_bot.models.count_tokens(
            #     contents=[input+self.sys_pro], model="gemini-2.0-flash"))
            # print(response.usage_metadata.dict())
            tokens = self._count_tokens(response)
            self._save_chat(chat, id)
            print(tokens)
            return response, tokens

    def _get_cur_cost(self):
        """
        return per mil token cost
        returns:
                TUPLE(input,output)

            """
        return os.environ.get('GM_INPUT_PRICE', 0), os.environ.get('GM_OUTPUT,PRICE', 0)

    def _count_tokens(self, res, content=None):
        inp_cost, out_cost = 0, 0
        if self.active_bot_name == 'gm_2.0_f':
            tokens = res.usage_metadata.dict()
            pprint(tokens)
            inp_cost, out_cost = self._get_cur_cost()
            tokens = {'output': tokens['candidates_token_count'],
                      'input': tokens['prompt_token_count'], 'inp_cost': inp_cost, 'out_cost': out_cost}
        total_cost = (
            inp_cost * tokens['inp_cost']/1000000) + (out_cost * tokens['output']/1000000)
        tokens['cost'] = total_cost
        return tokens


if __name__ == "__main__":
    b = Bot('test')
    r = b.responed(
        'Hi can you tell me a little about the large package for corporate go hosting? ')
    print(r)
