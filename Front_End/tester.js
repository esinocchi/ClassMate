async function sampleAPI() {
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

console.log(sampleAPI())