// Global state
let availabilityEntries = [];
let currentEditId = null;

// Day names for display
const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    loadAvailability();

    // Set up form submission
    document.getElementById('availabilityForm').addEventListener('submit', handleFormSubmit);

    // Show/hide temporary date fields based on type
    document.getElementById('availabilityType').addEventListener('change', function() {
        const temporaryGroup = document.getElementById('temporaryDatesGroup');
        temporaryGroup.style.display = this.value === 'temporary' ? 'grid' : 'none';
    });

    // Close modal when clicking outside
    document.getElementById('availabilityModal').addEventListener('click', function(e) {
        if (e.target === this) {
            closeAvailabilityModal();
        }
    });
});

// Load availability
async function loadAvailability() {
    try {
        const response = await fetch('/employee/availability');
        const data = await response.json();

        if (data.success) {
            availabilityEntries = data.availability || [];
            renderAvailabilityGrid();
        }
    } catch (error) {
        console.error('Error loading availability:', error);
        showNotification('Error loading availability', 'error');
    }
}

// Render weekly grid
function renderAvailabilityGrid() {
    for (let day = 0; day < 7; day++) {
        const daySlots = availabilityEntries.filter(a => a.day_of_week === day);
        const container = document.getElementById(`slots-${day}`);

        if (daySlots.length === 0) {
            container.innerHTML = '<div class="empty-day">No availability set</div>';
            continue;
        }

        container.innerHTML = daySlots.map(slot => {
            const typeLabel = slot.availability_type === 'recurring' ? '' :
                            slot.availability_type === 'temporary' ? ' (Temporary)' :
                            ' (Unavailable)';

            let dateRange = '';
            if (slot.availability_type === 'temporary' && (slot.effective_from || slot.effective_until)) {
                const from = slot.effective_from ? new Date(slot.effective_from).toLocaleDateString() : '?';
                const until = slot.effective_until ? new Date(slot.effective_until).toLocaleDateString() : '?';
                dateRange = `<div class="slot-type">${from} - ${until}</div>`;
            }

            return `
                <div class="availability-slot ${slot.availability_type}">
                    <div class="slot-time">${formatTime(slot.start_time)} - ${formatTime(slot.end_time)}</div>
                    ${typeLabel ? `<div class="slot-type">${typeLabel.substring(2)}</div>` : ''}
                    ${dateRange}
                    ${slot.notes ? `<div class="slot-type">${slot.notes}</div>` : ''}
                    <div class="slot-actions">
                        <button class="btn-edit" onclick="editAvailability(${slot.id})">Edit</button>
                        <button class="btn-delete" onclick="deleteAvailability(${slot.id})">Delete</button>
                    </div>
                </div>
            `;
        }).join('');
    }
}

// Open add availability modal
function openAddAvailabilityModal() {
    currentEditId = null;
    document.getElementById('modalTitle').textContent = 'Add Availability';
    document.getElementById('availabilityForm').reset();
    document.getElementById('temporaryDatesGroup').style.display = 'none';
    document.getElementById('availabilityModal').style.display = 'block';
}

// Close availability modal
function closeAvailabilityModal() {
    document.getElementById('availabilityModal').style.display = 'none';
    currentEditId = null;
}

// Edit availability
function editAvailability(id) {
    const slot = availabilityEntries.find(a => a.id === id);
    if (!slot) return;

    currentEditId = id;
    document.getElementById('modalTitle').textContent = 'Edit Availability';

    document.getElementById('dayOfWeek').value = slot.day_of_week;
    document.getElementById('startTime').value = slot.start_time;
    document.getElementById('endTime').value = slot.end_time;
    document.getElementById('availabilityType').value = slot.availability_type || 'recurring';
    document.getElementById('notes').value = slot.notes || '';

    const temporaryGroup = document.getElementById('temporaryDatesGroup');
    if (slot.availability_type === 'temporary') {
        temporaryGroup.style.display = 'grid';
        document.getElementById('effectiveFrom').value = slot.effective_from || '';
        document.getElementById('effectiveUntil').value = slot.effective_until || '';
    } else {
        temporaryGroup.style.display = 'none';
    }

    document.getElementById('availabilityModal').style.display = 'block';
}

// Delete availability
async function deleteAvailability(id) {
    if (!confirm('Are you sure you want to remove this availability?')) {
        return;
    }

    try {
        const response = await fetch(`/employee/availability/${id}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showNotification('Availability removed successfully', 'success');
            await loadAvailability();
        } else {
            showNotification(data.error || 'Error removing availability', 'error');
        }
    } catch (error) {
        console.error('Error deleting availability:', error);
        showNotification('Error removing availability', 'error');
    }
}

// Handle form submission
async function handleFormSubmit(e) {
    e.preventDefault();

    const formData = {
        day_of_week: parseInt(document.getElementById('dayOfWeek').value),
        start_time: document.getElementById('startTime').value,
        end_time: document.getElementById('endTime').value,
        availability_type: document.getElementById('availabilityType').value,
        notes: document.getElementById('notes').value
    };

    // Add temporary dates if applicable
    if (formData.availability_type === 'temporary') {
        formData.effective_from = document.getElementById('effectiveFrom').value || null;
        formData.effective_until = document.getElementById('effectiveUntil').value || null;
    }

    // Validate times
    if (formData.start_time >= formData.end_time) {
        showNotification('End time must be after start time', 'error');
        return;
    }

    try {
        const url = currentEditId
            ? `/employee/availability/${currentEditId}`
            : '/employee/availability';

        const method = currentEditId ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showNotification(
                currentEditId ? 'Availability updated successfully' : 'Availability added successfully',
                'success'
            );
            closeAvailabilityModal();
            await loadAvailability();
        } else {
            showNotification(data.error || 'Error saving availability', 'error');
        }
    } catch (error) {
        console.error('Error saving availability:', error);
        showNotification('Error saving availability', 'error');
    }
}

// Format time for display
function formatTime(timeString) {
    if (!timeString) return '';

    // Handle HH:MM or HH:MM:SS format
    const parts = timeString.split(':');
    const hours = parseInt(parts[0]);
    const minutes = parts[1];

    const period = hours >= 12 ? 'PM' : 'AM';
    const displayHours = hours === 0 ? 12 : hours > 12 ? hours - 12 : hours;

    return `${displayHours}:${minutes} ${period}`;
}

// Show notification
function showNotification(message, type = 'success') {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.className = `notification ${type}`;
    notification.style.display = 'block';

    setTimeout(() => {
        notification.style.display = 'none';
    }, 4000);
}
