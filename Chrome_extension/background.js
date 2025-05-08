console.log('Background script running');

let loggingEnabled = true; // Initial state: logging is enabled

// Function to set the logging state in storage
function setLoggingState(state) {
  loggingEnabled = state;
  chrome.storage.sync.set({ 'loggingEnabled': state }, () => {
    console.log('Logging enabled state set to ' + state);
  });
}

// Function to get the logging state from storage
function getLoggingState() {
  chrome.storage.sync.get(['loggingEnabled'], (result) => {
    loggingEnabled = result.loggingEnabled === undefined ? true : result.loggingEnabled;
    console.log('Logging enabled state is ' + loggingEnabled);
  });
}

// Get the logging state when the background script starts
getLoggingState();

// Listen for messages from the popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.command === "toggleLogging") {
    loggingEnabled = message.loggingEnabled;
    setLoggingState(loggingEnabled);
    sendResponse({ result: "Logging toggled", loggingEnabled: loggingEnabled });
  }
});
