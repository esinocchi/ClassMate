import json
import os


BASE_DIR = "Penn State/Projects/CanvasAI/"
#Update on your own to before the actual CanvasAI directory e.g. mine is f"{BASE_DIR}CanvasAI/" to access anything

class Popup:
    def __init__(self):
        self.open_button_pressed = False
        self.chat_memory = [] #figure out format to store
        self.courses_avoided = []
        self.user_name = ""


    def press_open_button(self):
        if self.open_button_pressed:
            self.open_button_pressed = False
        else:
            self.open_button_pressed = True

        
    def serialize(self):
        object_to_json = json.dumps({"open_button_pressed": f"{self.open_button_pressed}",
                                      "courses_avoided": f"{self.courses_avoided}", 
                                      "user_name": f"{self.user_name}"}) #once chat memory format is figured out, add to serialize
       
        with open(f"{BASE_DIR}CanvasAI/Popup_data/{self.user_name}.json", "w") as f:
            f.write(object_to_json)
        return "Data serialized succesfully"
    
    def deserialize(self):
        if not os.path.isdir(f"{BASE_DIR}CanvasAI/Popup_data/{self.user_name}.json"):
            return "ERROR: file doesn't exist"
        try:
            with open(f"{BASE_DIR}CanvasAI/Popup_data/{self.user_name}.json", "r") as f:
                file_content = json.loads(f.read())
            self.open_button_pressed = file_content.get("open_button_pressed")
            self.courses_avoided = file_content.get("courses_avoided")
            self.user_name = file_content.get("user_name")
            return "Data deserialized succesfully"
        except:
            return "ERROR: data cannot be accessed"



            