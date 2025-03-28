dataHolder = [{"role": "assistant", "content": [{"message": "", "function": [""]}]},{"role": "user", "user_id": "holder", "domain": getURL(), "recentDocs": [""], "content": [""], "classes": [{"id": "", "name": "", "selected": false}]}];

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
<div id="toolbar" class="footer">
    <button id="clearPromptButton" class="toolbarChildButton">New Chat</button>
  </div>
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
    <span id="classesTitleText">Your Active Classes</span>
</div>
<div id="settingsContainer">
    <div id="classesBox">
        <div id="classesHolder">
        </div>
        <div class="footer">
            <button id="saveClassesButton" class="toolbarChildButton">Save Class Selections</button>
        </div>
    </div>
</div>
`

document.body.appendChild(settings)

saveClassesButton.addEventListener("click", () => {
    const checkboxes = document.querySelectorAll("#classesHolder input[type='checkbox']");
    const states = [];

    checkboxes.forEach((checkbox) => {
        // Extract classID by removing the prefix
        const classID = checkbox.id.replace("active-checkBox-", "");
        states[classID] = checkbox.checked; // Store checkbox state as boolean
    });

    chrome.storage.local.get(["Context_CanvasAI"], async function(result) {
        let Context = result.Context_CanvasAI || dataHolder;

        //check for existing id
        if (Context[1].user_id == "holder") {
            Context[1].user_id = await retrieveID(Context[1].domain);
        }
        
        for (let i = Context[1].classes.length - 1; i >= 0; i--) {
            //update selected value for store checkboxes (store as string for json purposes)
            Context[1].classes[i].selected = states[`${Context[1].classes[i].name}`]
        }

        await pushClasses(Context[1].user_id, Context[1].domain, Context[1].classes)
        chrome.storage.local.set({ Context_CanvasAI: Context}, function() {});
    }); 


});

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
    let response = '';
    promptEntryBox.value = ''; // Clear the prompt entry box

    if (!prompt) {
        return;
    }
    try {

        const dynamicBoxesContainer = document.getElementById("dynamicBoxesContainer");
        
        dynamicBoxesContainer.classList.add("used"); // Adds 'used' class to dynamicBoxesContainer for any additional styling

        // Create and append loading spinner
        const loadingSpinner = document.createElement("div");
        loadingSpinner.classList.add("loading-spinner"); // Ensure you have CSS for this class
        loadingSpinner.innerHTML = `<div class="loader"></div>`; // Adjust styling in CSS
        dynamicBoxesContainer.appendChild(loadingSpinner);

        dynamicBoxesContainer.scrollTop = dynamicBoxesContainer.scrollHeight; // Keeps the scroll position at the bottom


        // Wait for the promptPairs to be updated in local storage
        await new Promise((resolve, reject) => {
            chrome.storage.local.get(["Context_CanvasAI"], async function(result) {
                let promptPairs = result.Context_CanvasAI || dataHolder;

                //check if the id is already stored
                if (promptPairs[1].user_id == "holder") {
                    promptPairs[1].user_id = await retrieveID(promptPairs[1].domain);
                }

                // If the list is longer than 20, pop the last index and add the new prompt-response pair
                if (promptPairs[0].content.length > 19) {
                    promptPairs[0].content.pop();
                    promptPairs[1].content.pop();
                }
                
                if(promptPairs[1].content[0] === ""){
                    promptPairs[1].content[0] = prompt;
                } else {
                    console.log("appending to old data")
                    promptPairs[0].content.unshift({"message": "", 
                                                    "function": [""]}); // Add the new prompt to the front
                    promptPairs[1].content.unshift(prompt);
                }

                try {
                    console.log(promptPairs);

                    const updated = await mainPipelineEntry({"context": promptPairs}); // Update memory of response based on pipeline return

                    console.log("notes info", updated.context[0].content[0].function[0])
                    console.log(updated.context[0].content[0].message)
                    //check for pdf notes output
                    if(updated.context[0].content[0].function[0] == "create_notes" && updated.context[0].content[0].message != "") {
                        response = [updated.context[0].content[0].message, true]
                    } else {
                        response = updated.context[0].content[0].message; // Update response for display
                    }

                    console.log(response)
                    
                    // Save updated list back to local storage
                    chrome.storage.local.set({ Context_CanvasAI: updated.context}, function() {
                        resolve(updated.context); // Resolve the promise with updated data
                });
                } catch (error) {
                    reject(error); // Reject the promise in case of error in mainPipelineEntry
                }
            });
        });

        // Remove loading spinner after adding memory box
        loadingSpinner.remove();

        if (Array.isArray(response)){
            addMemoryBox(prompt, response, true); //add memory box for display
        } else {
            addMemoryBox(prompt, response, false); //add memory box for display
        }

    } catch (error) {
        console.error("Error during prompt handling:", error);
    }

    promptEntryBox.select(); // Select the input box to prepare for the next prompt
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
}

//create memory box for previous chats
function addMemoryBox(prompt, response, downloadlink) {
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

    if (downloadlink == true) {
        const downloadButton = document.createElement("button");
        downloadButton.classList.add("toolbarChildButton")
        downloadButton.style.width = "40%";
        downloadButton.textContent = "download";
        memoryBox.appendChild(downloadButton);

        downloadButton.addEventListener("click", function(event) {
            chrome.storage.local.get(["Context_CanvasAI"], async function(result) {
                let context = result.Context_CanvasAI || dataHolder;

                if (context[1].user_id == "holder") {
                    context[1].user_id = await retrieveID(context[1].domain);
                }

                pullPDF(context[1].user_id, context[1].domain);
            });
        });
    }

    const dynamicBoxesContainer = document.getElementById("dynamicBoxesContainer");

    // Append memoryBox to dynamicBoxesContainer
    dynamicBoxesContainer.appendChild(memoryBox);




    dynamicBoxesContainer.classList.add("used"); // Adds 'used' class to dynamicBoxesContainer for any additional styling

// Ensure the container scrolls to the bottom
dynamicBoxesContainer.scrollTop = dynamicBoxesContainer.scrollHeight; // Keeps the scroll position at the bottom

// Simulate typing effect for response
let index = 0; // Initialize index to keep track of which character we're typing
const typingSpeed = 2; // Speed of typing effect
const responseLength = response.length; // Length of the response text

dynamicBoxesContainer.style.overflow = 'hidden'; // Hide overflow during typing to prevent scrolling
dynamicBoxesContainer.scrollTop = dynamicBoxesContainer.scrollHeight; // Ensure the container is at the bottom when typing starts

// Create the interval for typing effect
const interval = setInterval(() => {
    if (index < responseLength) {
        // Add the character at the current index to the innerHTML of the responseBox
        // Use slice() to progressively add content up to the current index + 1
        // REPLACEMENT: Replaced 'textContent' with 'innerHTML' to allow HTML formatting (e.g., <br> for line breaks)
        responseBox.innerHTML = response.slice(0, index + 1).replace(/\n/g, '<br>'); // Convert newlines to <br> tags

        // Scroll to the bottom of the container
        dynamicBoxesContainer.scrollTop = dynamicBoxesContainer.scrollHeight; // Keeps the scroll position at the bottom

        index++; // Increment index to type the next character
    } else {
        clearInterval(interval); // Stop the typing effect when done
        dynamicBoxesContainer.style.overflow = 'auto'; // Allow overflow after typing is complete
    }
}, typingSpeed); // Set typing speed (interval between each character typed)

    }

//rebuild class selections and past chats
async function rebuildPage() {
    try {
        await new Promise((resolve, reject) => {
            try{
                chrome.storage.local.get(["Context_CanvasAI"], async function(result) {
                    //update domain each reload
                    let context = result.Context_CanvasAI || dataHolder;

                    context[1].domain = getURL();

                    //check for existing id
                    if (context[1].user_id == "holder") {
                        context[1].user_id = await retrieveID(context[1].domain);
                    }

                    console.log(context)

                    for (let i = context[0].content.length - 1; i >= 0; i--) {
                        addMemoryBox(context[1].content[i], context[0].content[i].message, false); //reload chat history context based on storage
                    };

                    if (context[1].classes[0].id == ""){
                         context[1].classes = await retrieveClassList(context[1].user_id, context[1].domain);
                    }
                    for (let i = context[1].classes.length - 1; i >= 0; i--) {
                        addClassSetting(context[1].classes[i].name, context[1].classes[i].selected); //reload classes based on storage
                    };

                    // Save updated list back to local storage
                    chrome.storage.local.set({ Context_CanvasAI: context}, function() {
                        console.log("context set");
                        resolve(context); // Resolve the promise with updated data
                    });
                }); 
            } catch (error) {
                console.log("error rebuilding")
                reject(error);
            }
        });
    } catch (error) {
        console.error("Error during id fetching:", error);
    }
}

//clear chat memory
function clearMemory() {
    resetAllMemory();
    //set memory == to 0
    chrome.storage.local.get(["Context_CanvasAI"], function(result) {
        // Default to an empty structure if "Context_CanvasAI" doesn't exist
        let context = result.Context_CanvasAI || dataHolder;
        
        // Modify the context portion of the structure
        context[1].content = [""];
        context[0].content = [{"message":"", "function": [""]}];
    
        // Save the updated structure
        chrome.storage.local.set({ "Context_CanvasAI": context }, function() {});
    });

    let parent = document.getElementById("dynamicBoxesContainer"); 
    // Loop through children in reverse order and remove
    [...parent.children].forEach(child => {
        child.remove();
    });
}

//pull current URL of website
function getURL() {
    const currentUrl = window.location.href;
    const parsedUrl = new URL(currentUrl);
    const hostname = parsedUrl.hostname
    return hostname;    
}

function resetAllMemory() {
    chrome.storage.local.set({ Context_CanvasAI: dataHolder }, function() {
        console.log("memory reset to base model")
    });
    chrome.storage.local.get(["Context_CanvasAI"], function(result) {
        console.log(result.Context_CanvasAI);
    });
}

//below this are await helper functions




//below this is API calls


async function mainPipelineEntry(contextJSON) {
    console.log("\nentering Pipeline\n")
    try {
        const response = await fetch(`https://canvasclassmate.me/endpoints/mainPipelineEntry`,{
            method: 'POST',
            headers: {
                'Content-Type': 'application/json', 
            },
            body: JSON.stringify(contextJSON),
        }); 

        //check for error
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const data = await response.json();  // Wait for the JSON data
        console.log(data);  // { Sample: 'Sample API Return', Example: 'Sample Response' }
        return data;  // Return the data
    } catch (error) {
        console.error('Error calling API:', error);
        return false;  // Return false if there's an error
    }
}

async function retrieveClassList(studentID, domain) {
    console.log("\nretrieving Classes\n")
    //returned in the form dictionary {"id": "classNumber", "name": "className", "selected": false}
    try {
        const url = new URL("https://canvasclassmate.me/endpoints/pullCourses");
        url.searchParams.append("user_id", studentID);
        url.searchParams.append("domain", domain);
        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`API request failed with status: ${response.status}`);
        }

        const data = await response.json(); // Correctly parse the JSON response
        console.log("courseData",data.courses);
        //update stored data
        chrome.storage.local.get(["Context_CanvasAI"], function(result) {
            // Default to an empty structure if "Context_CanvasAI" doesn't exist
            let context = result.Context_CanvasAI || dataHolder;
    
            // Modify the classes portion of the structure
            context[1].classes = data.courses;
    
            // Save the updated structure
            chrome.storage.local.set({ "Context_CanvasAI": context }, function() {});
        });

        return data.courses;
    } catch (error) {
        console.error('Error calling API:', error);
        return false;  // Return false if there's an error
    }
}

async function retrieveID(domain) {
    console.log("\nretrieving ID\n");
    //returned in the form {"user_id": int}
    try {
        const response = await fetch(`https://canvasclassmate.me/endpoints/initiate_user?domain=${domain}`);
        const id_return = await response.json(); // Add await here
        console.log(`\nfetched ID: `); // Access as object property
        console.log(id_return.user_id.toString());
        return id_return.user_id.toString(); // Correct property access
    } catch (error) {
        console.error('Error calling API:', error);
        return false;
    }
}

async function pushClasses(id, domain, classes){
    console.log("attempting class push");
    let boolean1 = await isUpdating(id, domain);
    console.log(boolean1);
    console.log("classes", classes);
    if (boolean1 == false) {
        try {
            //add new pydantic model for pass
            const requestBody = {
                user_id: id,
                domain: domain,
                classes: classes
            };
            const response = await fetch(`https://canvasclassmate.me/endpoints/pushCourses`,{
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json', 
                },
                body: JSON.stringify(requestBody),
            });
            return true
        } catch (error) {
            return false;
        }
    } else {
        return false;
    }

}

async function isUpdating(user_id, domain){
    try {
            const response = await fetch(`https://canvasclassmate.me/endpoints/check_update_status?user_id=${user_id}&domain=${domain}`);
            const updating = await response.json(); // Add await here
            return updating
    } catch (error) {
        console.log("error1")
        return false;
    }
}

async function pullPDF(user_id, domain) {
    try {
        const response = await fetch(`https://canvasclassmate.me/endpoints/pullNotes?user_id=${user_id}&domain=${domain}`);

        if (!response.ok) {
            console.error('Failed to download document');
            return;
        }
    
        const blob = await response.blob();  // Convert the response to a Blob object
        const url = URL.createObjectURL(blob);
    
        // Open the PDF in a new tab
        window.open(url, '_blank');
    } catch (error) {
        console.log("error pulling pdf")
        return false;
    }
}