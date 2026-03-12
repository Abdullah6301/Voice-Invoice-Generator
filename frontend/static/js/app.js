/**
 * Invoice Generator Dashboard JavaScript
 * Handles API communication and UI interactions.
 */

const API_BASE = '/api';
let CONTRACTOR_ID = null;
let currentInvoiceId = null;
let sessionId = 'session_' + Date.now();

// ===== API Helper =====
async function apiCall(endpoint, method = 'GET', body = null) {
    const options = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };
    if (body) {
        options.body = JSON.stringify(body);
    }
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, options);
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'API error');
        }
        return data;
    } catch (error) {
        console.error(`API Error (${endpoint}):`, error);
        showToast(error.message, 'error');
        throw error;
    }
}

// ===== Load Current User =====
let _userReady;
const userReady = new Promise(resolve => { _userReady = resolve; });

async function loadCurrentUser() {
    try {
        const data = await apiCall('/contractors/me');
        if (data.contractor) {
            CONTRACTOR_ID = data.contractor.id;
        }
    } catch (e) {
        // Not logged in — page-level auth redirect handles this
    }
    _userReady();
}

// Auto-load user on any page that includes app.js
loadCurrentUser();

// ===== Toast Notifications =====
function showToast(message, type = 'info') {
    // Remove existing toasts
    document.querySelectorAll('.toast').forEach(t => t.remove());

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    requestAnimationFrame(() => toast.classList.add('show'));
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ===== Text-to-Speech =====
function speak(text) {
    if (!('speechSynthesis' in window)) return;
    // Cancel any ongoing speech
    window.speechSynthesis.cancel();
    // Clean text for speech (remove markdown-like formatting)
    const clean = text.replace(/[•\n]/g, '. ').replace(/\s+/g, ' ').trim();
    if (!clean) return;
    const utterance = new SpeechSynthesisUtterance(clean);
    utterance.lang = 'en-US';
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    window.speechSynthesis.speak(utterance);
}

function speakAndWait(text) {
    return new Promise((resolve) => {
        if (!('speechSynthesis' in window)) { resolve(); return; }
        window.speechSynthesis.cancel();
        const clean = text.replace(/[\u2022\n]/g, '. ').replace(/\s+/g, ' ').trim();
        if (!clean) { resolve(); return; }
        const utterance = new SpeechSynthesisUtterance(clean);
        utterance.lang = 'en-US';
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        utterance.onend = () => resolve();
        utterance.onerror = () => resolve();
        window.speechSynthesis.speak(utterance);
    });
}

// ===== Send Handler =====
function sendMessage() {
    sendConversationMessage();
}

// ===== Conversation Chat =====
function addChatBubble(sender, text, extra) {
    const container = document.getElementById('chatMessages');
    if (!container) return;

    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${sender}`;

    const label = document.createElement('div');
    label.className = 'chat-label';
    label.textContent = sender === 'user' ? 'You' : 'Invoice AI';
    bubble.appendChild(label);

    const msg = document.createElement('div');
    msg.textContent = text;
    bubble.appendChild(msg);

    // TTS button for AI messages
    if (sender === 'ai') {
        const ttsBtn = document.createElement('button');
        ttsBtn.className = 'tts-btn';
        ttsBtn.innerHTML = '&#128264;';
        ttsBtn.title = 'Listen';
        ttsBtn.onclick = () => speak(text);
        bubble.appendChild(ttsBtn);
    }

    // Extra content (invoice card, etc.)
    if (extra) {
        const div = document.createElement('div');
        div.innerHTML = extra;
        bubble.appendChild(div);
    }

    container.appendChild(bubble);
    container.scrollTop = container.scrollHeight;
}

async function sendConversationMessage() {
    const input = document.getElementById('voiceInput');
    const text = input.value.trim();
    if (!text) {
        showToast('Please enter a message', 'error');
        return;
    }

    // Show user message
    addChatBubble('user', text);
    input.value = '';

    try {
        const data = await apiCall('/conversation', 'POST', {
            text: text,
            contractor_id: CONTRACTOR_ID,
            session_id: sessionId,
        });

        if (data.success) {
            let extra = '';
            // If an invoice was created, show a card
            if (data.invoice) {
                currentInvoiceId = data.invoice.id;
                const inv = data.invoice;
                extra = `<div class="chat-invoice-card">`;
                extra += `<strong>Invoice ${inv.invoice_number}</strong><br>`;
                extra += `Total: $${(inv.total || 0).toFixed(2)}<br>`;
                if (data.pdf_path) {
                    const filename = data.pdf_path.split(/[/\\]/).pop();
                    extra += `<a href="/invoices/output/${filename}" target="_blank">&#128196; Download PDF</a>`;
                }
                extra += `</div>`;
                // Refresh dashboard stats
                if (typeof loadDashboardStats === 'function') loadDashboardStats();
            }

            addChatBubble('ai', data.response, extra);

            // Auto-speak the AI response
            speak(data.response);
        } else {
            addChatBubble('ai', data.response || 'Something went wrong.');
        }
    } catch (error) {
        addChatBubble('ai', 'Sorry, I encountered an error. Please try again.');
    }
}

async function resetConversation() {
    try {
        await apiCall('/conversation/reset', 'POST', {
            contractor_id: CONTRACTOR_ID,
            session_id: sessionId,
        });
    } catch (_) { /* ignore */ }
    sessionId = 'session_' + Date.now();
    const container = document.getElementById('chatMessages');
    if (container) container.innerHTML = '';
    addChatBubble('ai', 'Ready for a new order. Describe your order naturally.');
}

// ===== Dashboard Stats =====
async function loadDashboardStats() {
    await userReady;
    try {
        const [invoicesData, datasetData] = await Promise.all([
            apiCall(`/invoices?contractor_id=${CONTRACTOR_ID}`),
            apiCall('/dataset'),
        ]);

        const allInvoices = invoicesData.invoices || [];
        const totalItems = datasetData.count || 0;

        const today = new Date();
        const todayStr = today.toISOString().slice(0, 10);
        const monthStr = today.toISOString().slice(0, 7);

        const todaysInvoices = allInvoices.filter(inv => (inv.created_at || '').slice(0, 10) === todayStr);
        const todaysRevenue = todaysInvoices.reduce((sum, inv) => sum + (inv.total || 0), 0);

        const monthInvoices = allInvoices.filter(inv => (inv.created_at || '').slice(0, 7) === monthStr);
        const monthRevenue = monthInvoices.reduce((sum, inv) => sum + (inv.total || 0), 0);

        document.getElementById('statInvoices').textContent = todaysInvoices.length;
        const todayRevEl = document.getElementById('statTodayRevenue');
        if (todayRevEl) todayRevEl.textContent = `$${todaysRevenue.toFixed(2)}`;
        const monthRevEl = document.getElementById('statMonthRevenue');
        if (monthRevEl) monthRevEl.textContent = `$${monthRevenue.toFixed(2)}`;
        document.getElementById('statDataset').textContent = totalItems;

        // Load recent invoices
        if (invoicesData.invoices && invoicesData.invoices.length > 0) {
            displayRecentInvoices(invoicesData.invoices.slice(0, 5));
        }
    } catch (error) {
        console.error('Failed to load dashboard stats:', error);
    }
}

function displayRecentInvoices(invoices) {
    const tbody = document.getElementById('recentInvoicesBody');
    if (!tbody) return;

    if (invoices.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No invoices yet</td></tr>';
        return;
    }

    tbody.innerHTML = invoices.map(inv => `
        <tr>
            <td>${inv.invoice_number}</td>
            <td>${inv.customer_name || 'N/A'}</td>
            <td>$${(inv.total || 0).toFixed(2)}</td>
            <td><span class="badge badge-${inv.status}">${inv.status}</span></td>
            <td>${new Date(inv.created_at).toLocaleDateString()}</td>
        </tr>
    `).join('');
}

// ===== Customers =====
async function loadCustomers() {
    await userReady;
    try {
        const searchInput = document.getElementById('customerSearch');
        const search = searchInput ? searchInput.value.trim() : '';
        const url = search
            ? `/customers?contractor_id=${CONTRACTOR_ID}&search=${encodeURIComponent(search)}`
            : `/customers?contractor_id=${CONTRACTOR_ID}`;
        const data = await apiCall(url);
        displayCustomers(data.customers || []);
    } catch (error) {
        console.error('Failed to load customers:', error);
    }
}

function displayCustomers(customers) {
    const tbody = document.getElementById('customersBody');
    if (!tbody) return;

    if (customers.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No customers found</td></tr>';
        return;
    }

    tbody.innerHTML = customers.map(c => `
        <tr>
            <td>${c.id}</td>
            <td><strong>${c.name}</strong></td>
            <td>${c.phone || '-'}</td>
            <td>${c.email || '-'}</td>
            <td>${c.address || '-'}</td>
            <td>
                <button class="btn btn-sm btn-outline" onclick="editCustomer(${c.id})">Edit</button>
                <button class="btn btn-sm btn-danger" onclick="deleteCustomer(${c.id})">Delete</button>
            </td>
        </tr>
    `).join('');
}

async function createCustomer(event) {
    event.preventDefault();
    const form = event.target;
    const data = {
        contractor_id: CONTRACTOR_ID,
        name: form.name.value,
        phone: form.phone.value,
        email: form.email.value,
        address: form.address.value,
        city: form.city.value,
        state: form.state.value,
        zip_code: form.zip_code.value,
        notes: form.notes.value,
    };

    try {
        await apiCall('/customers', 'POST', data);
        showToast('Customer created successfully', 'success');
        form.reset();
        closeModal('customerModal');
        loadCustomers();
    } catch (error) {
        console.error('Create customer error:', error);
    }
}

async function deleteCustomer(id) {
    if (!confirm('Are you sure you want to delete this customer?')) return;
    try {
        await apiCall(`/customers/${id}`, 'DELETE');
        showToast('Customer deleted', 'success');
        loadCustomers();
    } catch (error) {
        console.error('Delete customer error:', error);
    }
}

// ===== Invoices =====
async function loadInvoices() {
    await userReady;
    try {
        const data = await apiCall(`/invoices?contractor_id=${CONTRACTOR_ID}`);
        displayInvoices(data.invoices || []);
    } catch (error) {
        console.error('Failed to load invoices:', error);
    }
}

function displayInvoices(invoices) {
    const tbody = document.getElementById('invoicesBody');
    if (!tbody) return;

    if (invoices.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No invoices yet. Use voice commands to create one!</td></tr>';
        return;
    }

    tbody.innerHTML = invoices.map(inv => `
        <tr>
            <td>${inv.invoice_number}</td>
            <td>${inv.customer_name || 'N/A'}</td>
            <td>${inv.project_location || '-'}</td>
            <td>$${(inv.total || 0).toFixed(2)}</td>
            <td><span class="badge badge-${inv.status}">${inv.status}</span></td>
            <td>${new Date(inv.created_at).toLocaleDateString()}</td>
            <td>
                <button class="btn btn-sm btn-outline" onclick="viewInvoice(${inv.id})">View</button>
                <button class="btn btn-sm btn-primary" onclick="editInvoice(${inv.id})">Edit</button>
                ${inv.status === 'draft' ? `<button class="btn btn-sm btn-success" onclick="finalizeInvoice(${inv.id})">Finalize</button>` : ''}
                ${inv.pdf_path ? `<a href="/invoices/output/${inv.pdf_path.split(/[/\\\\]/).pop()}" target="_blank" class="btn btn-sm btn-accent">PDF</a>` : ''}
                <button class="btn btn-sm btn-danger" onclick="deleteInvoice(${inv.id})">Delete</button>
            </td>
        </tr>
    `).join('');
}

async function viewInvoice(id) {
    try {
        const data = await apiCall(`/invoices/${id}`);
        const inv = data.invoice;
        currentInvoiceId = inv.id;

        let html = `<h3>Invoice ${inv.invoice_number}</h3>`;
        html += `<p>Status: <span class="badge badge-${inv.status}">${inv.status}</span></p>`;
        html += `<p>Total: <strong>$${(inv.total || 0).toFixed(2)}</strong></p>`;

        if (inv.items && inv.items.length > 0) {
            html += '<table class="data-table" style="margin-top:12px"><thead><tr><th>Item</th><th>Qty</th><th>Unit</th><th>Price</th><th>Total</th></tr></thead><tbody>';
            for (const item of inv.items) {
                html += `<tr><td>${item.item_name}</td><td>${item.quantity}</td><td>${item.unit || 'each'}</td><td>$${(item.unit_price||0).toFixed(2)}</td><td>$${(item.total_price||0).toFixed(2)}</td></tr>`;
            }
            html += '</tbody></table>';
        }

        const modal = document.getElementById('viewModal');
        document.getElementById('viewModalContent').innerHTML = html;
        modal.classList.add('active');
    } catch (error) {
        console.error('View invoice error:', error);
    }
}

async function finalizeInvoice(id) {
    if (!confirm('Finalize this invoice and generate PDF?')) return;
    try {
        const data = await apiCall(`/finalize-invoice/${id}`, 'POST');
        showToast('Invoice finalized! PDF generated.', 'success');
        loadInvoices();
    } catch (error) {
        console.error('Finalize error:', error);
    }
}

async function deleteInvoice(id) {
    if (!confirm('Are you sure you want to delete this invoice?')) return;
    try {
        await apiCall(`/invoices/${id}`, 'DELETE');
        showToast('Invoice deleted', 'success');
        loadInvoices();
    } catch (error) {
        console.error('Delete invoice error:', error);
    }
}

// ===== Dataset =====
async function loadDataset() {
    await userReady;
    try {
        const searchInput = document.getElementById('datasetSearch');
        const categorySelect = document.getElementById('categoryFilter');
        const search = searchInput ? searchInput.value.trim() : '';
        const category = categorySelect ? categorySelect.value : '';

        let url = '/dataset';
        if (search) url += `?search=${encodeURIComponent(search)}`;
        else if (category) url += `?category=${encodeURIComponent(category)}`;

        const data = await apiCall(url);
        displayDataset(data.items || []);

        // Update item count badge
        const countBadge = document.getElementById('itemCount');
        if (countBadge) countBadge.textContent = `${data.count || 0} items`;

        // Load categories for filter
        if (categorySelect && categorySelect.options.length <= 1) {
            const catData = await apiCall('/dataset/categories');
            for (const cat of catData.categories || []) {
                const option = document.createElement('option');
                option.value = cat;
                option.textContent = cat;
                categorySelect.appendChild(option);
            }
        }
    } catch (error) {
        console.error('Failed to load dataset:', error);
    }
}

function displayDataset(items) {
    const tbody = document.getElementById('datasetBody');
    if (!tbody) return;

    if (items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No items found</td></tr>';
        return;
    }

    tbody.innerHTML = items.map(item => `
        <tr>
            <td>${item.csi_code || '-'}</td>
            <td><strong>${item.item_name}</strong></td>
            <td><span class="badge" style="background:#edf2f7;color:#2d3748">${item.category}</span></td>
            <td>${item.unit}</td>
            <td>$${(item.material_cost || 0).toFixed(2)}</td>
            <td>$${(item.labor_cost || 0).toFixed(2)}</td>
            <td><strong>$${(item.total_price || 0).toFixed(2)}</strong></td>
            <td>
                <button class="btn btn-sm btn-primary" onclick="openEditItemModal(${item.item_id})">Edit</button>
                <button class="btn btn-sm btn-danger" onclick="deleteDatasetItem(${item.item_id}, '${item.item_name.replace(/'/g, "\\'")}')">Delete</button>
            </td>
        </tr>
    `).join('');
}

// ===== Dataset CRUD =====
function openAddItemModal() {
    document.getElementById('datasetModalTitle').textContent = 'Add Item';
    document.getElementById('dsSubmitBtn').textContent = 'Add Item';
    document.getElementById('dsItemId').value = '';
    document.getElementById('dsItemName').value = '';
    document.getElementById('dsCategory').value = '';
    document.getElementById('dsUnit').value = '';
    document.getElementById('dsCsiCode').value = '';
    document.getElementById('dsMaterialCost').value = '0';
    document.getElementById('dsLaborCost').value = '0';
    document.getElementById('dsTotalPrice').value = '0';
    openModal('datasetItemModal');
}

async function openEditItemModal(itemId) {
    try {
        const data = await apiCall(`/dataset/${itemId}`);
        const item = data.item;
        document.getElementById('datasetModalTitle').textContent = 'Edit Item';
        document.getElementById('dsSubmitBtn').textContent = 'Save Changes';
        document.getElementById('dsItemId').value = item.item_id;
        document.getElementById('dsItemName').value = item.item_name || '';
        document.getElementById('dsCategory').value = item.category || '';
        document.getElementById('dsUnit').value = item.unit || '';
        document.getElementById('dsCsiCode').value = item.csi_code || '';
        document.getElementById('dsMaterialCost').value = item.material_cost || 0;
        document.getElementById('dsLaborCost').value = item.labor_cost || 0;
        document.getElementById('dsTotalPrice').value = item.total_price || 0;
        openModal('datasetItemModal');
    } catch (error) {
        console.error('Load item error:', error);
    }
}

async function saveDatasetItem(event) {
    event.preventDefault();
    const itemId = document.getElementById('dsItemId').value;
    const payload = {
        item_name: document.getElementById('dsItemName').value.trim(),
        category: document.getElementById('dsCategory').value.trim().toUpperCase(),
        unit: document.getElementById('dsUnit').value.trim(),
        csi_code: document.getElementById('dsCsiCode').value.trim(),
        material_cost: parseFloat(document.getElementById('dsMaterialCost').value) || 0,
        labor_cost: parseFloat(document.getElementById('dsLaborCost').value) || 0,
        total_price: parseFloat(document.getElementById('dsTotalPrice').value) || 0,
    };
    try {
        if (itemId) {
            await apiCall(`/dataset/${itemId}`, 'PUT', payload);
            showToast('Item updated successfully!', 'success');
        } else {
            await apiCall('/dataset', 'POST', payload);
            showToast('Item added successfully!', 'success');
        }
        closeModal('datasetItemModal');
        loadDataset();
    } catch (error) {
        console.error('Save dataset item error:', error);
    }
}

async function deleteDatasetItem(itemId, itemName) {
    if (!confirm(`Delete "${itemName}"? This cannot be undone.`)) return;
    try {
        await apiCall(`/dataset/${itemId}`, 'DELETE');
        showToast('Item deleted.', 'success');
        loadDataset();
    } catch (error) {
        console.error('Delete dataset item error:', error);
    }
}

// ===== Settings =====
async function loadSettings() {
    await userReady;
    try {
        const data = await apiCall(`/contractors/${CONTRACTOR_ID}`);
        const c = data.contractor;
        if (c) {
            const form = document.getElementById('settingsForm');
            if (form) {
                form.company_name.value = c.company_name || '';
                form.owner_name.value = c.owner_name || '';
                form.email.value = c.email || '';
                form.phone.value = c.phone || '';
                form.address.value = c.address || '';
            }
        }
    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

async function saveSettings(event) {
    event.preventDefault();
    const form = event.target;
    const data = {
        company_name: form.company_name.value,
        owner_name: form.owner_name.value,
        phone: form.phone.value,
        address: form.address.value,
    };

    try {
        await apiCall(`/contractors/${CONTRACTOR_ID}`, 'PUT', data);
        showToast('Profile updated successfully', 'success');
    } catch (error) {
        console.error('Save settings error:', error);
    }
}

// ===== Modal Helpers =====
function openModal(id) {
    document.getElementById(id).classList.add('active');
}

function closeModal(id) {
    document.getElementById(id).classList.remove('active');
}

// ===== Invoice Edit =====
let editInvoiceData = null;
let editCustomersList = [];

async function editInvoice(id) {
    try {
        const [invData, custData] = await Promise.all([
            apiCall(`/invoices/${id}`),
            apiCall(`/customers?contractor_id=${CONTRACTOR_ID}`),
        ]);
        editInvoiceData = invData.invoice;
        editCustomersList = custData.customers || [];

        document.getElementById('editInvoiceId').value = id;
        document.getElementById('editModalTitle').textContent = `Edit ${editInvoiceData.invoice_number}`;
        document.getElementById('editLocation').value = editInvoiceData.project_location || '';
        document.getElementById('editPaymentTerms').value = editInvoiceData.payment_terms || 'Due on Receipt';
        document.getElementById('editNotes').value = editInvoiceData.notes || '';

        // Populate customer dropdown
        const sel = document.getElementById('editCustomerId');
        sel.innerHTML = editCustomersList.map(c =>
            `<option value="${c.id}" ${c.id === editInvoiceData.customer_id ? 'selected' : ''}>${c.name}</option>`
        ).join('');

        // Populate items
        renderEditItems(editInvoiceData.items || []);
        updateEditTotal();

        openModal('editModal');
    } catch (error) {
        console.error('Edit invoice error:', error);
    }
}

function renderEditItems(items) {
    const tbody = document.getElementById('editItemsBody');
    if (!tbody) return;
    tbody.innerHTML = items.map(item => `
        <tr data-item-id="${item.id}">
            <td><input type="text" class="form-input ei-name" value="${item.item_name}" style="padding:6px 8px;font-size:13px"></td>
            <td><input type="number" class="form-input ei-qty" value="${item.quantity}" step="any" min="0" style="padding:6px 8px;font-size:13px;width:65px" onchange="updateEditTotal()"></td>
            <td><input type="text" class="form-input ei-unit" value="${item.unit || 'each'}" style="padding:6px 8px;font-size:13px;width:65px"></td>
            <td><input type="number" class="form-input ei-price" value="${(item.unit_price || 0).toFixed(2)}" step="0.01" min="0" style="padding:6px 8px;font-size:13px;width:85px" onchange="updateEditTotal()"></td>
            <td class="ei-total" style="font-weight:600">$${(item.total_price || 0).toFixed(2)}</td>
            <td><button type="button" class="btn btn-sm btn-danger" onclick="removeEditRow(this, ${item.id})">&#10005;</button></td>
        </tr>
    `).join('');
}

function addEditRow() {
    const tbody = document.getElementById('editItemsBody');
    if (!tbody) return;
    const tr = document.createElement('tr');
    tr.setAttribute('data-item-id', 'new');
    tr.innerHTML = `
        <td><input type="text" class="form-input ei-name" placeholder="Item name" style="padding:6px 8px;font-size:13px"></td>
        <td><input type="number" class="form-input ei-qty" value="1" step="any" min="0" style="padding:6px 8px;font-size:13px;width:65px" onchange="updateEditTotal()"></td>
        <td><input type="text" class="form-input ei-unit" value="each" style="padding:6px 8px;font-size:13px;width:65px"></td>
        <td><input type="number" class="form-input ei-price" value="0.00" step="0.01" min="0" style="padding:6px 8px;font-size:13px;width:85px" onchange="updateEditTotal()"></td>
        <td class="ei-total" style="font-weight:600">$0.00</td>
        <td><button type="button" class="btn btn-sm btn-danger" onclick="this.closest('tr').remove();updateEditTotal()">&#10005;</button></td>
    `;
    tbody.appendChild(tr);
}

let editRemovedItemIds = [];

function removeEditRow(btn, itemId) {
    if (itemId && itemId !== 'new') {
        editRemovedItemIds.push(itemId);
    }
    btn.closest('tr').remove();
    updateEditTotal();
}

function updateEditTotal() {
    const rows = document.querySelectorAll('#editItemsBody tr');
    let total = 0;
    rows.forEach(row => {
        const qty = parseFloat(row.querySelector('.ei-qty')?.value || 0);
        const price = parseFloat(row.querySelector('.ei-price')?.value || 0);
        const lineTotal = qty * price;
        total += lineTotal;
        const td = row.querySelector('.ei-total');
        if (td) td.textContent = `$${lineTotal.toFixed(2)}`;
    });
    const display = document.getElementById('editTotalDisplay');
    if (display) display.textContent = `Total: $${total.toFixed(2)}`;
}

async function saveInvoiceEdits(event) {
    event.preventDefault();
    const invoiceId = parseInt(document.getElementById('editInvoiceId').value);

    try {
        // 1. Update invoice header
        await apiCall(`/invoices/${invoiceId}`, 'PUT', {
            customer_id: parseInt(document.getElementById('editCustomerId').value),
            project_location: document.getElementById('editLocation').value,
            payment_terms: document.getElementById('editPaymentTerms').value,
            notes: document.getElementById('editNotes').value,
        });

        // 2. Remove deleted items
        for (const itemId of editRemovedItemIds) {
            await apiCall('/remove-item', 'POST', { invoice_id: invoiceId, item_id: itemId });
        }
        editRemovedItemIds = [];

        // 3. Update existing items and add new ones
        const rows = document.querySelectorAll('#editItemsBody tr');
        for (const row of rows) {
            const itemId = row.getAttribute('data-item-id');
            const name = row.querySelector('.ei-name')?.value?.trim();
            const qty = parseFloat(row.querySelector('.ei-qty')?.value || 0);
            const unit = row.querySelector('.ei-unit')?.value?.trim() || 'each';
            const price = parseFloat(row.querySelector('.ei-price')?.value || 0);
            if (!name) continue;

            if (itemId === 'new') {
                await apiCall('/add-item', 'POST', {
                    invoice_id: invoiceId,
                    item_name: name,
                    quantity: qty,
                    unit_price: price,
                    unit: unit,
                });
            } else {
                await apiCall(`/invoice-items/${itemId}`, 'PUT', {
                    item_name: name,
                    quantity: qty,
                    unit_price: price,
                    unit: unit,
                });
            }
        }

        // 4. Re-finalize if it was finalized
        if (editInvoiceData && editInvoiceData.status === 'finalized') {
            await apiCall(`/finalize-invoice/${invoiceId}`, 'POST');
        }

        showToast('Invoice updated successfully!', 'success');
        closeModal('editModal');
        if (typeof loadInvoices === 'function') loadInvoices();
        if (typeof loadDashboardStats === 'function') loadDashboardStats();
    } catch (error) {
        console.error('Save invoice edits error:', error);
    }
}

// ===== Enter Key for Voice Input =====
document.addEventListener('DOMContentLoaded', () => {
    const voiceInput = document.getElementById('voiceInput');
    if (voiceInput) {
        voiceInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
    }
});

// ============================================================
// ===== Voice Conversation System ============================
// ============================================================

let wsContractorProfile = {};
let allWorkspaceItems = [];

const VoiceConversation = (() => {
    let recognition = null;
    let isActive = false;
    let isListening = false;
    let isProcessing = false;
    let conversationDone = false;
    const supported = !!(window.SpeechRecognition || window.webkitSpeechRecognition);

    function initRecognition() {
        if (recognition) return;
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SR();
        recognition.lang = 'en-US';
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;

        recognition.onstart = () => { isListening = true; };

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript.trim();
            if (transcript && !isProcessing) {
                addChatBubble('user', transcript);
                processText(transcript);
            }
        };

        recognition.onend = () => {
            isListening = false;
            if (isActive && !isProcessing && !conversationDone) {
                setTimeout(() => {
                    if (isActive && !isProcessing && !conversationDone) startRecognition();
                }, 400);
            }
        };

        recognition.onerror = (event) => {
            isListening = false;
            if (event.error === 'no-speech' || event.error === 'aborted') {
                if (isActive && !isProcessing && !conversationDone) {
                    setTimeout(() => {
                        if (isActive && !isProcessing) startRecognition();
                    }, 400);
                }
            } else if (event.error === 'not-allowed') {
                showToast('Microphone access denied. Please allow mic access in browser settings.', 'error');
                setIndicator('error');
            }
        };
    }

    function startRecognition() {
        if (!recognition || isListening) return;
        try { recognition.start(); } catch (e) {}
    }

    function stopRecognition() {
        isListening = false;
        if (recognition) { try { recognition.stop(); } catch (e) {} }
    }

    async function start() {
        if (!supported) {
            showToast('Speech recognition not supported. Use Chrome or Edge.', 'error');
            return;
        }
        isActive = true;
        conversationDone = false;
        isProcessing = false;
        sessionId = 'session_' + Date.now();
        initRecognition();

        // Show workspace, hide other sections
        document.getElementById('voiceStarter').style.display = 'none';
        document.getElementById('voiceWorkspace').style.display = 'grid';
        const stats = document.getElementById('statsSection');
        const recent = document.getElementById('recentSection');
        if (stats) stats.style.display = 'none';
        if (recent) recent.style.display = 'none';
        document.getElementById('chatMessages').innerHTML = '';
        document.getElementById('wsStopText').textContent = 'End Conversation';

        // Load contractor profile and dataset items in parallel
        await userReady;
        try {
            const [cData, dData] = await Promise.all([
                apiCall(`/contractors/${CONTRACTOR_ID}`),
                apiCall('/dataset'),
            ]);
            wsContractorProfile = cData.contractor || {};
            allWorkspaceItems = dData.items || [];
            renderWorkspaceItems(allWorkspaceItems);
        } catch (e) {
            wsContractorProfile = {};
            allWorkspaceItems = [];
        }

        // Initialize empty preview
        updateInvoicePreview({});

        // Send initial message to start the conversation flow
        setIndicator('processing');
        await processText('I want to create a new invoice', true);
    }

    function stop() {
        isActive = false;
        conversationDone = false;
        isProcessing = false;
        window.speechSynthesis.cancel();
        stopRecognition();

        apiCall('/conversation/reset', 'POST', {
            contractor_id: CONTRACTOR_ID,
            session_id: sessionId,
        }).catch(() => {});

        // Restore UI
        document.getElementById('voiceStarter').style.display = '';
        document.getElementById('voiceWorkspace').style.display = 'none';
        const stats = document.getElementById('statsSection');
        const recent = document.getElementById('recentSection');
        if (stats) stats.style.display = '';
        if (recent) recent.style.display = '';
        loadDashboardStats();
    }

    async function processText(text, isInitial = false) {
        if (isProcessing && !isInitial) return;
        isProcessing = true;
        stopRecognition();
        setIndicator('processing');

        try {
            const data = await apiCall('/conversation', 'POST', {
                text: text,
                contractor_id: CONTRACTOR_ID,
                session_id: sessionId,
            });

            if (data.success) {
                if (data.state) updateInvoicePreview(data.state);

                if (data.invoice) {
                    handleComplete(data);
                    return;
                }

                addChatBubble('ai', data.response);
                setIndicator('speaking');
                await speakAndWait(data.response);

                if (isActive && !conversationDone) {
                    setIndicator('listening');
                    isProcessing = false;
                    startRecognition();
                    return;
                }
            }
        } catch (e) {
            addChatBubble('ai', 'Sorry, an error occurred. Please try again.');
            if (isActive && !conversationDone) {
                setIndicator('listening');
                isProcessing = false;
                startRecognition();
                return;
            }
        }
        isProcessing = false;
    }

    function handleComplete(data) {
        const inv = data.invoice;
        let extra = '<div class="chat-invoice-card">';
        extra += `<strong>Invoice ${inv.invoice_number}</strong><br>`;
        extra += `Total: $${(inv.total || 0).toFixed(2)}<br>`;
        if (data.pdf_path) {
            const filename = data.pdf_path.split(/[\/\\]/).pop();
            extra += `<a href="/invoices/output/${filename}" target="_blank">&#128196; Download PDF</a>`;
        }
        extra += '</div>';

        addChatBubble('ai', data.response, extra);
        updateInvoicePreview(data.state, inv);

        conversationDone = true;
        isProcessing = false;
        setIndicator('done');
        document.getElementById('wsStopText').textContent = 'Close';

        speakAndWait(data.response);
    }

    function setIndicator(state) {
        const el = document.getElementById('voiceIndicator');
        const txt = document.getElementById('voiceIndicatorText');
        if (!el || !txt) return;
        el.className = 'vi vi-' + state;
        const labels = {
            listening: 'Listening...', speaking: 'AI Speaking...',
            processing: 'Processing...', done: 'Invoice Complete', error: 'Error',
        };
        txt.textContent = labels[state] || '';
    }

    return { start, stop, processText, isSupported: supported };
})();

// ===== Workspace Helpers =====

function updateInvoicePreview(state, finalInvoice) {
    const el = document.getElementById('invoicePreview');
    if (!el) return;
    const cp = wsContractorProfile || {};
    const date = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

    if (finalInvoice) {
        // Show finalized invoice
        const inv = finalInvoice;
        const items = inv.items || [];
        const itemsHtml = items.map((item, i) => `
            <tr>
                <td>${i + 1}</td>
                <td>${item.item_name}</td>
                <td>${item.quantity} ${item.unit || 'each'}</td>
                <td>$${(item.unit_price || 0).toFixed(2)}</td>
                <td>$${(item.total_price || 0).toFixed(2)}</td>
            </tr>
        `).join('');
        const pdfLink = inv.pdf_path
            ? `<div class="preview-download"><a href="/invoices/output/${inv.pdf_path.split(/[\/\\]/).pop()}" target="_blank" class="btn btn-success">&#128196; Download PDF</a></div>`
            : '';
        el.innerHTML = `
            <div class="preview-invoice">
                <div class="preview-header">
                    <h2>INVOICE</h2>
                    <span class="preview-badge finalized">Finalized</span>
                </div>
                <div class="preview-meta">
                    <span>${date}</span>
                    <span>${inv.invoice_number}</span>
                </div>
                <div class="preview-parties">
                    <div class="preview-party">
                        <strong>From</strong>
                        <div>${cp.company_name || 'Your Company'}</div>
                        <div>${cp.owner_name || ''}</div>
                        <div>${cp.address || ''}</div>
                        <div>${cp.phone || ''}${cp.email ? ' | ' + cp.email : ''}</div>
                    </div>
                    <div class="preview-party">
                        <strong>Bill To</strong>
                        <div>${inv.customer_name || state.customer_name || '---'}</div>
                    </div>
                </div>
                <div class="preview-location"><strong>Project:</strong> ${inv.project_location || state.project_location || '---'}</div>
                <table class="preview-items-table">
                    <thead><tr><th>#</th><th>Item</th><th>Qty</th><th>Price</th><th>Total</th></tr></thead>
                    <tbody>${itemsHtml}</tbody>
                </table>
                <div class="preview-totals">
                    <div class="total-line">Subtotal: $${(inv.subtotal || inv.total || 0).toFixed(2)}</div>
                    <div class="total-line grand-total">Total: $${(inv.total || 0).toFixed(2)}</div>
                </div>
                ${pdfLink}
            </div>
        `;
        return;
    }

    // Show draft preview from conversation state
    const customerName = state.customer_name || '';
    const location = state.project_location || '';
    const items = state.items || [];
    let subtotal = 0;
    items.forEach(item => {
        subtotal += (item.matched_item?.total_price || 0) * item.quantity;
    });

    let itemsHtml = '';
    if (items.length === 0) {
        itemsHtml = '<tr><td colspan="5" class="empty-row">No items yet</td></tr>';
    } else {
        items.forEach((item, i) => {
            const price = item.matched_item?.total_price || 0;
            const total = price * item.quantity;
            itemsHtml += `<tr>
                <td>${i + 1}</td>
                <td>${item.material}</td>
                <td>${item.quantity} ${item.unit}</td>
                <td>$${price.toFixed(2)}</td>
                <td>$${total.toFixed(2)}</td>
            </tr>`;
        });
    }

    el.innerHTML = `
        <div class="preview-invoice">
            <div class="preview-header">
                <h2>INVOICE</h2>
                <span class="preview-badge">Draft Preview</span>
            </div>
            <div class="preview-meta">
                <span>${date}</span>
                <span>INV-DRAFT</span>
            </div>
            <div class="preview-parties">
                <div class="preview-party">
                    <strong>From</strong>
                    <div>${cp.company_name || 'Your Company'}</div>
                    <div>${cp.owner_name || ''}</div>
                    <div>${cp.address || ''}</div>
                    <div>${cp.phone || ''}${cp.email ? ' | ' + cp.email : ''}</div>
                </div>
                <div class="preview-party">
                    <strong>Bill To</strong>
                    ${customerName
                        ? `<div>${customerName}</div>`
                        : '<div class="placeholder">Waiting for customer name...</div>'}
                </div>
            </div>
            <div class="preview-location">
                <strong>Project:</strong> ${location || '<span class="placeholder">Waiting for location...</span>'}
            </div>
            <table class="preview-items-table">
                <thead><tr><th>#</th><th>Item</th><th>Qty</th><th>Price</th><th>Total</th></tr></thead>
                <tbody>${itemsHtml}</tbody>
            </table>
            <div class="preview-totals">
                <div class="total-line">Subtotal: $${subtotal.toFixed(2)}</div>
                <div class="total-line grand-total">Total: $${subtotal.toFixed(2)}</div>
            </div>
        </div>
    `;
}

function renderWorkspaceItems(items) {
    const el = document.getElementById('wsItemsList');
    if (!el) return;
    if (items.length === 0) {
        el.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-light)">No items found</div>';
        return;
    }
    el.innerHTML = items.map(item => `
        <div class="ws-item-row">
            <div>
                <div class="ws-item-name">${item.item_name}</div>
                <div class="ws-item-cat">${item.category}</div>
            </div>
            <div style="text-align:right">
                <div class="ws-item-price">$${(item.total_price || 0).toFixed(2)}</div>
                <div class="ws-item-unit">per ${item.unit}</div>
            </div>
        </div>
    `).join('');
}

function filterWorkspaceItems() {
    const search = (document.getElementById('wsItemsSearch')?.value || '').toLowerCase().trim();
    if (!search) { renderWorkspaceItems(allWorkspaceItems); return; }
    const filtered = allWorkspaceItems.filter(item =>
        item.item_name.toLowerCase().includes(search) ||
        item.category.toLowerCase().includes(search)
    );
    renderWorkspaceItems(filtered);
}

function wsSendText() {
    const input = document.getElementById('wsTextInput');
    const text = input?.value.trim();
    if (!text) return;
    input.value = '';
    addChatBubble('user', text);
    VoiceConversation.processText(text);
}
