function setExample(text) {
    document.getElementById('claim-input').value = text;
}

async function verifyClaim() {
    const input = document.getElementById('claim-input').value.trim();
    const resultDiv = document.getElementById('result');
    const btn = document.getElementById('verify-btn');

    if (!input) {
        return;
    }

    btn.disabled = true;
    btn.innerHTML = 'Verifying<span class="loader"></span>';
    resultDiv.className = 'result hidden';

    try {
        const response = await fetch('/api/verify', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({claim: input})
        });

        const data = await response.json();
        displayResult(data);
    } catch (error) {
        resultDiv.className = 'result unverified';
        resultDiv.innerHTML = `
            <h3>❌ Error</h3>
            <p>Failed to verify claim: ${error.message}</p>
        `;
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Verify';
    }
}

function displayResult(data) {
    const resultDiv = document.getElementById('result');
    let className = 'result ';
    let icon = '';
    let title = '';
    let content = '';

    if (data.status === 'verified') {
        className += 'verified';
        icon = '✓';
        title = 'Verified';
        content = `
            <p><strong>Route:</strong> ${data.route}</p>
            ${data.equation ? `<p><strong>Equation:</strong> ${data.equation}</p>` : ''}
            <p><strong>Confidence:</strong> ${(data.confidence * 100).toFixed(1)}%</p>
            <div class="result-details">
                Execution time: ${data.execution_time_ms}ms
            </div>
        `;
    } else if (data.status === 'unverified') {
        className += 'unverified';
        icon = '✗';
        title = 'Unverified';
        content = `
            <p>The claim could not be verified.</p>
            <p><strong>Route:</strong> ${data.route}</p>
            <div class="result-details">
                Execution time: ${data.execution_time_ms}ms
            </div>
        `;
    } else if (data.status === 'insufficient_info') {
        className += 'insufficient';
        icon = '⚠';
        title = 'Insufficient Information';
        content = `
            <p>${data.suggested_clarification}</p>
            <p><strong>Missing:</strong> ${data.reason_code.replace(/_/g, ' ')}</p>
            <p><strong>Detected values:</strong> ${data.detected_values.join(', ')}</p>
            <div class="result-details">
                Execution time: ${data.execution_time_ms}ms
            </div>
        `;
    } else if (data.status === 'no_claim') {
        className += 'no-claim';
        icon = '⦻';
        title = 'No Claim Detected';
        content = `
            <p>${data.message}</p>
            <div class="result-details">
                Execution time: ${data.execution_time_ms}ms
            </div>
        `;
    }

    resultDiv.className = className;
    resultDiv.innerHTML = `
        <h3>${icon} ${title}</h3>
        ${content}
    `;
}

document.getElementById('claim-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        verifyClaim();
    }
});
