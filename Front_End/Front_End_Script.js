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
const imageUrl2 = chrome.runtime.getURL('images/button.png');
chat.innerHTML = `
<div class = "header">
    <span id= "titleText">What can we help you with?</span>
</div>
<div id="dynamicBoxesContainer"></div>
<div class="footer">
    <textarea id = "promptEntryBox" placeholder = "Ask me anything..."></textarea>
    <button id = "promptEntryButton">
        <img src="${imageUrl2}" alt="NotFound" height="35px" width="35px">
    </button>
</div>
`;

document.body.appendChild(chat);

//Give button functionality
promptEntryButton.addEventListener("click", () => {
    handlePrompt();
});

document.addEventListener("keydown", function(event) {
    if (event.key === 'Enter') {
        event.preventDefault();
        handlePrompt();
    }
});

window.addEventListener("load", () => {
    console.log('page reloading')
    rebuildPage();
});

  function handlePrompt() {
    // Get and remove value from the prompt entry box
    let prompt = promptEntryBox.value;
    let response = ''; // Default response can be set here, e.g. "sample response"
    promptEntryBox.value = ''; // Clear the prompt entry box
    promptEntryBox.select(); // Select the input box to prepare for the next prompt

    if (!prompt) {
        return;
    }

    chrome.storage.local.get(["previousChats"], function(result) {
        // Default to an empty array if "previousChats" doesn't exist
        let promptPairs = result.previousChats || [];

        // If the list is longer than 20, pop the last one and add the new prompt-response pair
        if (promptPairs.length > 19) {
            promptPairs.pop(); // Remove the last element
        }
        
        promptPairs.unshift([prompt, "sample response"]); // Add new prompt-response pair to the front

        // Save updated list back to local storage
        chrome.storage.local.set({ previousChats: promptPairs }, function() {
            console.log("Updated list:", promptPairs); // Log the updated list (not 'tuples')
        });

        // Create a new box to hold the prompt and response
        const dynamicBoxesContainer = document.getElementById("dynamicBoxesContainer");
        addMemoryBox(prompt, "sample response"); // Call the function to add the new box to the UI
    });
}

function toggleChat() {
    if (chat.classList.contains("open")) {
        chat.classList.remove("open")
    } else {
        chat.classList.add("open")
        promptEntryBox.select()
    }
}

function sendToBackend(prompt) {

}

function addMemoryBox(prompt, response) {
    if (prompt == '') {
        return -1
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

    function rebuildPage() {
        chrome.storage.local.get(["previousChats"], function(result) {
            let promptPairs = result.previousChats || [];

            for (let i = promptPairs.length - 1; i >= 0; i--) {
                const dynamicBoxesContainer = document.getElementById("dynamicBoxesContainer");
                addMemoryBox(promptPairs[i][0], promptPairs[i][1]);
            };
        });
    }