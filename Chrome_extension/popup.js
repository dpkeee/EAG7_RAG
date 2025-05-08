document.addEventListener('DOMContentLoaded', function() {
  const toggleButton = document.getElementById('toggleButton');
  let loggingEnabled = true; // Initial state in popup

  // Function to update the button text based on logging state
  function updateButtonText() {
    toggleButton.textContent = loggingEnabled ? 'Stop Logging' : 'Start Logging';
  }

  // Get the logging state from storage and update the button text
  chrome.storage.sync.get(['loggingEnabled'], (result) => {
    loggingEnabled = result.loggingEnabled === undefined ? true : result.loggingEnabled;
    updateButtonText();
  });

  toggleButton.addEventListener('click', function() {
    loggingEnabled = !loggingEnabled; // Toggle the state
    updateButtonText();

    // Send a message to the background script to toggle the logging state
    chrome.runtime.sendMessage({ command: "toggleLogging", loggingEnabled: loggingEnabled }, (response) => {
      console.log(response.result);
    });
  });

  // --- Search functionality ---
  const searchButton = document.getElementById('searchButton');
  const searchInput = document.getElementById('searchInput');
  const searchResult = document.getElementById('searchResult');
  const API_ENDPOINT = "http://127.0.0.1:8000/agent-search"; // Changed endpoint

  searchButton.addEventListener('click', async function() {
    const query = searchInput.value.trim();
    searchResult.textContent = "";
    if (!query) {
      searchResult.textContent = "Please enter some text to search.";
      return;
    }
    searchResult.textContent = "Searching...";
    try {
      // Use POST and send JSON body
      const response = await fetch(API_ENDPOINT, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ query })
      });
       
      if (!response.ok) {
        searchResult.textContent = `Error: ${response.statusText}`;
        return;
      }
      const data = await response.json();
      //alert("2.." + data.result);
      //alert("3.." + data.error);

      // The /agent-search endpoint returns { result: ... }
      if (data.result) {
        searchResult.innerHTML = `<b>Agent Result:</b> ${hyperlink_urls(data.result)}`;
      } else if (data.error) {
        searchResult.textContent = `Error: ${data.error}`;
      } else {
        searchResult.textContent = "No result returned.";
      }
    } catch (error) {
      searchResult.textContent = `Error: ${error.message}`;
    }
  });
});

function hyperlink_urls(text) {
  return text.replace(/(https?:\/\/[^\s\]\)]+)/g, function(match) {
    // Remove trailing commas from the URL
    let cleanUrl = match.replace(/,+$/, '');
    return `<a href="${cleanUrl}" target="_blank">${cleanUrl}</a>`;
  });
}
