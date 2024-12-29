// Create a container div for the box
let closed = true;

const box = document.createElement("div");
box.id = "Box";
const imageUrl = chrome.runtime.getURL('images/CanvasAILogo.png');
// Add content to the box
box.innerHTML = `
    <span></span>
    <img src="${imageUrl}" alt="NotFound" />
`;
// Append the box to the body
document.body.appendChild(box);

const chat = document.createElement("div");
chat.id = "ChatWindow";
const imageUrl2 = chrome.runtime.getURL('images/button.png');
chat.innerHTML = `
<span id= "titleText">What can we help you with?</span>
<textarea id = "promptEntryBox" placeholder = "Ask me anything..."></textarea>
<button id = "promptEntryButton"><img src="${imageUrl2}" alt="NotFound" height="35px" width="35px"></button>
`;
document.body.appendChild(chat);


box.addEventListener('click', () => {
    if (closed == true) {
        closed = false;
        openWindow();
    } else {
        closed = true
        closeWindow();
    }
});

function openWindow() {
    titleText.style.opacity = '1';
    titleText.style.right = '130px';

    promptEntryBox.style.opacity = '1';
    promptEntryBox.style.width = '330px';
    promptEntryBox.style.top = '25px';

    promptEntryButton.style.opacity = '1';
    promptEntryButton.style.width = '35px';
    promptEntryButton.style.height = '35px';
    promptEntryButton.style.top = '25px';

    chat.style.top = '5px';
    chat.style.right = '5px';
    chat.style.height = '120px';
    chat.style.width = '400px';
    chat.style.opacity = '1';
}

function closeWindow() {
    titleText.style.opacity = '0';
    titleText.style.right = '-140px'

    promptEntryBox.style.opacity = '0';
    promptEntryBox.style.width = '0px';

    promptEntryButton.style.opacity = '0';
    promptEntryButton.style.width = '0';
    promptEntryButton.style.height = '0';

    chat.style.top = '8px';
    chat.style.right = '8px';
    chat.style.height = '30px';
    chat.style.width = '65px';
    chat.style.opacity = '0';
}