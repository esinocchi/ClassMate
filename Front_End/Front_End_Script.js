// Create a container div for the box
let closed = true;

const box = document.createElement("div");
box.id = "Box";
const imageUrl = chrome.runtime.getURL('images/CanvasAILogo.png');
// Add content to the box
box.innerHTML = `
    <img src="${imageUrl}" alt="NotFound" />
`;
// Append the box to the body
document.body.appendChild(box);

//make initial div clickable
box.addEventListener("click", () => {
    toggleChat()
});

//Create interactable Chatbox
const chat = document.createElement("div");
chat.id = "ChatWindow";
const imageUrl2 = chrome.runtime.getURL('images/UpArrow.png');
const imageUrl3 = chrome.runtime.getURL('images/settings.png');
chat.innerHTML = `
<div class="header">
    <img src="${imageUrl3}" alt="NotFound" id="settingsIcon" height="20px" width="20px">
    <span id="titleText">What can we help you with?</span>
</div>
<div id="dynamicBoxesContainer"></div>
<div class="footer">
    <textarea id="promptEntryBox" placeholder = "Ask me anything..."></textarea>
    <button id="promptEntryButton">
        <img src="${imageUrl2}" alt="NotFound" height="35px" width="35px">
    </button>
</div>
`;

document.body.appendChild(chat);

//Create interactable Settingsbox
const settings = document.createElement("div");
settings.id = "SettingsWindow";
const imageUrl4 = chrome.runtime.getURL('images/BackArrow.png');
settings.innerHTML = `
<div class="header">
    <img src="${imageUrl4}" alt="NotFound" id="homeArrow" height="20px" width="20px">
    <span id="settingsTitleText">Settings</span>
</div>
<div id="settingsContainer">
    <div class="settingsChild">
        <span id="clearPromptLabel" class="settingsChildLabel">Clear Prompt History:</span>
        <button id="clearPromptButton" class="settingsChildButton">Clear History</button>
    </div>
    <div id="classesBox">
        <div class="header">
            <span id="classesTitleText">Your Active Classes</span>
        </div>
        <div id="classesHolder">
        </div>
    </div>
</div>
`

document.body.appendChild(settings)

//Give settings button functionality
settingsIcon.addEventListener("click", () => {
    openSettings();
});

//give clear memory button functionality
clearPromptButton.addEventListener("click", () => {
    clearMemory();
});

//give back arrow functionality
homeArrow.addEventListener("click", () => {
    settings.classList.remove("open");
    toggleChat();
});

//Give prompt button functionality
promptEntryButton.addEventListener("click", () => {
    handlePrompt();
});

//Submit prompt with enter key
document.addEventListener("keydown", function(event) {
    if (event.key === 'Enter') {
        event.preventDefault();
        handlePrompt();
    }
});

//reload past chats and class settings on page load
window.addEventListener("load", () => {
    rebuildPage();
});

//main functionality for prompt handling
async function handlePrompt() {
    // Get and remove value from the prompt entry box
    let prompt = promptEntryBox.value;
    let response = ''; // Default response can be set here, e.g. "sample response"
    promptEntryBox.value = ''; // Clear the prompt entry box
    let promptPairs = [];
    promptEntryBox.select(); // Select the input box to prepare for the next prompt

    if (!prompt) {
        return;
    }

    // Wait for the promptPairs to be updated in local storage
    await new Promise((resolve) => {
        chrome.storage.local.get(["previousChats_CanvasAI"], function(result) {
            // Default to an empty array if "previousChats_CanvasAI" doesn't exist
            promptPairs = result.previousChats_CanvasAI || [];

            // If the list is longer than 20, pop the last one and add the new prompt-response pair
            if (promptPairs.length > 19) {
                promptPairs.pop();
            }

            promptPairs.unshift([prompt, "sample response"]); // Add the new prompt to the front

            // Save updated list back to local storage
            chrome.storage.local.set({ previousChats_CanvasAI: promptPairs }, function() {
                resolve(); // Resolve the promise to continue
            });
        });
    });

    const APIdata = await sampleAPI();

    // Create a new box to hold the prompt and response
    const dynamicBoxesContainer = document.getElementById("dynamicBoxesContainer");
    console.log(APIdata)
    addMemoryBox(prompt, "sample response");
}

//open settings window
function openSettings() {
    if(chat.classList.contains("open")) {
        chat.classList.remove("open")
    }
    settings.classList.add("open")
}

//close settings window
function closeSettings() {
    if(settings.classList.contains("open")) {
        settings.classList.remove("open")
    }
    chat.classList.add("open")
}

//open or close chatbox
function toggleChat() {
    //ensure that settings closes upon interaction
    if (settings.classList.contains("open")) {
        settings.classList.remove("open")
    //close chat if open and open chat if closed
    } else if (chat.classList.contains("open")) {
        chat.classList.remove("open")
    } else {
        chat.classList.add("open")
        promptEntryBox.select()
    }
}

//add class checkbox and title to settings page
function addClassSetting(classID, checked) {
    //create parent div
    const ClassBox = document.createElement("div");
    ClassBox.classList.add("settingsChild");

    //create name label
    const classLabel = document.createElement("span");
    classLabel.classList.add("settingsChildLabel");
    classLabel.innerText = classID + ":";

    //create checkbox
    const activeToggle = document.createElement("div");
    let currID = "active-checkBox-" + classID;
    activeToggle.classList.add("checkbox-wrapper-49")

    //create box based on checked parameter
    activeToggle.innerHTML = `
        <div class="block">
            <input data-index="0" id="${currID}" type="checkbox" ${checked ? 'checked' : ''} />
            <label for="${currID}"></label>
        </div>
    `
    activeToggle.classList.add("settingsToggle")

    //append pieces and add to document
    ClassBox.appendChild(classLabel);
    ClassBox.appendChild(activeToggle);

    const classesHolder = document.getElementById("classesHolder");
    classesHolder.appendChild(ClassBox);

    //event listener to update class selection memory based on changes
    current = document.getElementById(currID);
    current.addEventListener("change",  (event) => {
        const checkboxName = event.target.id;
        const isChecked = event.target.checked;

        //pull local storage data based on ID of event triggerer
        chrome.storage.local.get(["ClassSelections_CanvasAI"], function(result) {
            let ClassSelections = result.ClassSelections_CanvasAI || [];
            for (let i = ClassSelections.length - 1; i >= 0; i--) {
                if(ClassSelections[i][0] == checkboxName.replace("active-checkBox-", "")){
                    ClassSelections[i][1] = isChecked;
                    chrome.storage.local.set({ ClassSelections_CanvasAI: ClassSelections}, function() {});
                    break;
                }
            }
            }); 
        });
}

//create memory box for previous chats
function addMemoryBox(prompt, response) {
    if (prompt == '') {
        return -1;
    }

    const memoryBox = document.createElement("div");
    memoryBox.classList.add("promptMemoryBox");

    // Create prompt box element
    const promptBox = document.createElement("div");
    promptBox.classList.add("promptBox");
    promptBox.innerText = prompt;

    // Create response box with typing effect
    const responseBox = document.createElement("div");
    responseBox.classList.add("responseBox");

    // Append prompt and response boxes to memoryBox
    memoryBox.appendChild(promptBox);
    memoryBox.appendChild(responseBox);

    const dynamicBoxesContainer = document.getElementById("dynamicBoxesContainer");

    // Append memoryBox to dynamicBoxesContainer
    dynamicBoxesContainer.appendChild(memoryBox);

    dynamicBoxesContainer.classList.add("used");

    dynamicBoxesContainer.scrollTop = dynamicBoxesContainer.scrollHeight;

    // Simulate typing effect for response
    let index = 0;
    const typingSpeed = 2; 
    const responseLength = response.length;

    dynamicBoxesContainer.style.overflow = 'hidden';
    dynamicBoxesContainer.scrollTop = dynamicBoxesContainer.scrollHeight;

    const interval = setInterval(() => {
        if (index < responseLength) {
            responseBox.textContent += response.charAt(index);
            dynamicBoxesContainer.scrollTop = dynamicBoxesContainer.scrollHeight;
            index++;
        } else {
            clearInterval(interval); 
            dynamicBoxesContainer.style.overflow = 'auto';
        }
    }, typingSpeed);
    }

//rebuild class selections and past chats
function rebuildPage() {
    chrome.storage.local.get(["previousChats_CanvasAI"], function(result) {
        let promptPairs = result.previousChats_CanvasAI || [];
        for (let i = promptPairs.length - 1; i >= 0; i--) {
            addMemoryBox(promptPairs[i][0], promptPairs[i][1]);
        };
    });

    chrome.storage.local.get(["ClassSelections_CanvasAI"], function(result) {
        let ClassSelections = result.ClassSelections_CanvasAI || [];
        for (let i = ClassSelections.length - 1; i >= 0; i--) {
            addClassSetting(ClassSelections[i][0], ClassSelections[i][1]);
        }; 
    });
}

//process new list of classes and update memory
function processClassList(classes) {
    //process list in form [class, checked] into chrome memory
    chrome.storage.local.set({ ClassSelections_CanvasAI: classes}, function() {});
}

//clear chat memory
function clearMemory() {
    //set memory == to 0
    let promptPairs = []
    chrome.storage.local.set({ previousChats_CanvasAI: promptPairs }, function() {});

    let parent = document.getElementById("dynamicBoxesContainer"); 
    // Loop through children in reverse order and remove
    [...parent.children].forEach(child => {
        child.remove();
    });
}

//pull current URL of website
function getURL() {
    let currentUrl = window.location.href;
    return currentUrl;    
}

//pull states of classes
function getCheckboxStates() {
    const checkboxes = document.querySelectorAll('input[type="checkbox"][data-class-id]');
    const checkboxStates = new Set();

    checkboxes.forEach(checkbox => {
        const classId = checkbox.getAttribute('data-class-id');
        const state = checkbox.checked ? 'checked' : 'unchecked';
        checkboxStates.add([classId, state]);
    });

    return checkboxStates;
}


//below this are await helper functions




//below this is API calls


async function sampleAPI() {
    console.log("FETCHING COMENSE");
    try {
        const response = await fetch('https://canvasclassmate.me/');  // Correct the URL here
        const data = await response.json();  // Wait for the JSON data
        console.log(data);  // { Sample: 'Sample API Return', Example: 'Sample Response' }
        return data;  // Return the data
    } catch (error) {
        console.error('Error calling API:', error);
        return false;  // Return false if there's an error
    }
}