
export async function sampleAPI() {
    fetch('https://3.133.153.53/:8000/')
    .then(response => response.json())
    .then(data => {
        console.log(data);  // { Sample: 'Sample API Return', Example: 'Sample Response' }
        return data
    })
    .catch(error => {
        console.error('Error calling API:', error);
        return false
    });
}