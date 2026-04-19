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
            body: JSON.stringify({ claim: input })
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

function renderComparison(comparison) {
    if (!comparison) {
        return '';
    }

    const llmIcon = comparison.llm_only === 'VALID' ? '✓' : (comparison.llm_only === 'INVALID' ? '✗' : '?');
    const verifierIcon = comparison.llm_plus_verifier === 'VALID' ? '✓' : (comparison.llm_plus_verifier === 'INVALID' ? '✗' : '∑');

    return `
        <h4 style="margin-top: 1.5rem; margin-bottom: 1rem; font-size: 1.125rem; font-weight: 600; color: #1d1d1f;">⚖️ Compare LLM vs Verifier</h4>
        <div class="comparison-grid">
            <div class="comparison-box llm-only">
                <h4>LLM Only</h4>
                <p class="comparison-result">${llmIcon} ${comparison.llm_only}</p>
                <p class="comparison-label">Probabilistic reasoning</p>
            </div>
            <div class="comparison-box verifier">
                <h4>LLM + Verifier</h4>
                <p class="comparison-result">${verifierIcon} ${comparison.llm_plus_verifier}</p>
                <p class="comparison-label">Deterministic formal route</p>
            </div>
        </div>
        <div class="verdict ${comparison.verdict.toLowerCase()}">
            <strong>Verdict:</strong> ${comparison.verdict_message}
        </div>
    `;
}

function renderCitations(citations) {
    if (!Array.isArray(citations) || citations.length === 0) {
        return '';
    }

    const items = citations.map((citation) => {
        const source = citation.url
            ? `<a href="${citation.url}" target="_blank" rel="noopener noreferrer">${citation.title}</a>`
            : citation.title;
        const stance = citation.stance || 'neutral';
        return `
            <li class="citation-item">
                <div>
                    <strong>${source}</strong>
                    <span class="citation-score">(score ${citation.score})</span>
                    <span class="stance ${stance}">${stance}</span>
                </div>
                <div>${citation.snippet}</div>
            </li>
        `;
    }).join('');

    return `
        <h4 style="margin-top: 1.5rem; margin-bottom: 0.75rem; font-size: 1.125rem; font-weight: 600; color: #1d1d1f;">📚 Retrieved Evidence</h4>
        <ul class="citation-list">${items}</ul>
    `;
}

function renderEvidenceAssessment(assessment) {
    if (!assessment) {
        return '';
    }

    return `
        <p><strong>Evidence assessment:</strong>
            support=${assessment.support_count},
            contradiction=${assessment.contradiction_count},
            neutral=${assessment.neutral_count}
        </p>
    `;
}

function renderDetails(data) {
    return `
        <div class="result-details">
            Route: ${data.route || 'unknown'} | Type: ${data.claim_type || 'unknown'} | Execution time: ${data.execution_time_ms}ms
        </div>
    `;
}

function displayResult(data) {
    const resultDiv = document.getElementById('result');
    let className = 'result ';
    let icon = '';
    let title = '';
    let content = '';

    if (['verified', 'unverified', 'computed', 'error'].includes(data.status)) {
        if (data.status === 'verified') {
            className += 'verified';
            icon = '✅';
            title = 'Formally Verified';
        } else if (data.status === 'unverified') {
            className += 'unverified';
            icon = '❌';
            title = 'Formally Refuted';
        } else if (data.status === 'computed') {
            className += 'warning';
            icon = '∑';
            title = 'Computed (Not a Boolean Claim)';
        } else {
            className += 'critical';
            icon = '🚨';
            title = 'Verification Error';
        }

        const valueSection = data.solver_result && data.solver_result.value
            ? `<p><strong>Computed Value:</strong> ${data.solver_result.value}</p>`
            : '';

        content = `
            <p>${data.message || ''}</p>
            ${data.equation ? `<p><strong>Equation:</strong> ${data.equation}</p>` : ''}
            ${valueSection}
            ${renderComparison(data.comparison)}
            ${renderEvidenceAssessment(data.evidence_assessment)}
            ${renderCitations(data.citations)}
            ${renderDetails(data)}
        `;
    } else if (data.status === 'evidence_backed') {
        className += 'verified';
        icon = '📚';
        title = 'Evidence-Backed';
        content = `
            <p>${data.message || ''}</p>
            ${renderEvidenceAssessment(data.evidence_assessment)}
            ${renderCitations(data.citations)}
            ${renderDetails(data)}
        `;
    } else if (data.status === 'cannot_formally_verify') {
        className += 'insufficient';
        icon = '⚠';
        title = 'Cannot Formally Verify';
        content = `
            <p>${data.message || ''}</p>
            <p><strong>Reason:</strong> ${(data.reason || '').replace(/_/g, ' ')}</p>
            <p><strong>Suggested Clarification:</strong> ${data.suggested_clarification || 'Provide additional structured evidence or formal constraints.'}</p>
            ${renderEvidenceAssessment(data.evidence_assessment)}
            ${renderCitations(data.citations)}
            ${renderDetails(data)}
        `;
    } else if (data.status === 'insufficient_info') {
        className += 'insufficient';
        icon = '⚠';
        title = 'Insufficient Information';
        const detected = (data.detected_values || []).join(', ') || 'none';
        content = `
            <p>${data.message || ''}</p>
            <p><strong>Suggested Clarification:</strong> ${data.suggested_clarification || 'Please provide more details.'}</p>
            <p><strong>Missing:</strong> ${(data.missing_info || 'missing_information').replace(/_/g, ' ')}</p>
            <p><strong>Detected values:</strong> ${detected}</p>
            ${renderDetails(data)}
        `;
    } else if (data.status === 'llm_only') {
        className += 'warning';
        icon = '🧠';
        title = 'LLM-Only Result';
        const llm = data.llm_only || {};
        content = `
            <p>${data.message || ''}</p>
            <p><strong>LLM Status:</strong> ${llm.status || 'UNKNOWN'}</p>
            ${llm.verdict ? `<p><strong>Verdict:</strong> ${llm.verdict}</p>` : ''}
            ${llm.raw_response ? `<p><strong>Model Output:</strong> ${llm.raw_response}</p>` : ''}
            ${llm.error ? `<p><strong>Error:</strong> ${llm.error}</p>` : ''}
            ${renderDetails(data)}
        `;
    } else {
        className += 'no-claim';
        icon = '⦻';
        title = 'No Claim Detected';
        content = `
            <p>${data.message || 'No verifiable claim detected.'}</p>
            ${renderDetails(data)}
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
