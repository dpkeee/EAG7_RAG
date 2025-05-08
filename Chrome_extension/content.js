const API_ENDPOINT = "http://127.0.0.1:8000/";

const confidentialSites = [
    "mail.google.com",
    "web.whatsapp.com"
];

function shouldSkipSite(url) {
    return confidentialSites.some(site => url.includes(site));
}

async function sendURLToFastAPI(url) {
    try {
        const apiUrlWithParameter = `${API_ENDPOINT}?url=${encodeURIComponent(url)}`;

        const response = await fetch(apiUrlWithParameter, {
            method: "GET",
        });

        if (!response.ok) {
            console.error(`HTTP error! status: ${response.status}, statusText: ${response.statusText}`);
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log("FastAPI response:", data);
        // Process the embedding data received from FastAPI
    } catch (error) {
        console.error("Error sending text to FastAPI:", error);
    }
}

const currentURL = window.location.href;

if (shouldSkipSite(currentURL)) {
    console.log("Skipping confidential site:", currentURL);
} else {
    // Get the logging state from storage
    chrome.storage.sync.get(['loggingEnabled'], (result) => {
        const loggingEnabled = result.loggingEnabled === undefined ? true : result.loggingEnabled;

        if (loggingEnabled) {
            sendURLToFastAPI(currentURL); // Send the URL to FastAPI
        } else {
            console.log("Logging is disabled.  Skipping URL:", currentURL);
        }
    });
} 