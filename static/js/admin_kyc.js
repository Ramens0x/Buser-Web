$(document).ready(function () {
    function getAuthToken() {
        const loginDataString = localStorage.getItem('buser_login_data');
        if (!loginDataString) return null;
        try { return JSON.parse(loginDataString).token; } catch (e) { return null; }
    }

    const token = getAuthToken();
    if (!token) {
        window.location.href = "login.html";
        return;
    }

    let currentKycId = null;

    // Tải danh sách KYC
    function loadKycList() {
        $.ajax({
            url: `${API_URL}/api/admin/kyc-list`,
            type: 'GET',
            beforeSend: function (xhr) {
                xhr.setRequestHeader('Authorization', 'Bearer ' + token);
            },
            success: function (res) {
                const tableBody = $('#kyc-table-body');
                tableBody.empty();

                if (res.requests.length === 0) {
                    tableBody.html('<tr><td colspan="7" class="text-center">Chưa có yêu cầu KYC nào.</td></tr>');
                    return;
                }

                res.requests.forEach(kyc => {
                    let statusClass = 'status-pending';
                    let statusText = 'Chờ duyệt';
                    let actionButtons = `
                        <button class="btn btn-xs btn-primary btn-view-kyc" data-id="${kyc.id}">
                            <i class="fa fa-eye"></i> Xem
                        </button>`;

                    if (kyc.status === 'approved') {
                        statusClass = 'status-approved';
                        statusText = 'Đã duyệt';
                    } else if (kyc.status === 'rejected') {
                        statusClass = 'status-rejected';
                        statusText = 'Từ chối';
                    }

                    const row = `
                        <tr>
                            <td><strong>${escapeHTML(kyc.username)}</strong></td>
                            <td>${escapeHTML(kyc.full_name)}</td>
                            <td>${escapeHTML(kyc.id_number)}</td>
                            <td>
                            <img src="${API_URL}/api/kyc-image/${kyc.id_front}?token=${token}" class="kyc-image-thumb" onclick="window.open('${API_URL}/api/kyc-image/${kyc.id_front}?token=${token}', '_blank')">
                            </td>
                            <td>${kyc.submitted_at}</td>
                            <td><span class="${statusClass}">${statusText}</span></td>
                            <td>${actionButtons}</td>
                        </tr>`;
                    tableBody.append(row);
                });
            },
            error: function (xhr) {
                alert("Lỗi: " + xhr.responseJSON.message);
                window.location.href = "index.html";
            }
        });
    }

    // Xem chi tiết KYC
    $(document).on('click', '.btn-view-kyc', function () {
        const kycId = $(this).data('id');
        currentKycId = kycId;

        // Tìm KYC trong danh sách đã load
        $.ajax({
            url: `${API_URL}/api/admin/kyc-list`,
            type: 'GET',
            beforeSend: function (xhr) { xhr.setRequestHeader('Authorization', 'Bearer ' + token); },
            success: function (res) {
                const kyc = res.requests.find(k => k.id === kycId);
                if (!kyc) return;

                $('#modal-username').text(kyc.username);
                $('#modal-img-front').attr('src', `${API_URL}/api/kyc-image/${kyc.id_front}?token=${token}`);
                $('#modal-img-back').attr('src', `${API_URL}/api/kyc-image/${kyc.id_back_image}?token=${token}`);
                $('#modal-img-selfie').attr('src', `${API_URL}/api/kyc-image/${kyc.selfie_image}?token=${token}`);
                $('#modal-admin-note').val(kyc.admin_note || '');

                // Ẩn nút nếu đã duyệt/từ chối
                if (kyc.status !== 'pending') {
                    $('#btn-approve-kyc, #btn-reject-kyc').hide();
                } else {
                    $('#btn-approve-kyc, #btn-reject-kyc').show();
                }

                $('#kycModal').modal('show');
            }
        });
    });

    // Phê duyệt KYC
    $('#btn-approve-kyc').on('click', function () {
        if (!confirm('Xác nhận PHÊ DUYỆT KYC này?')) return;

        const adminNote = $('#modal-admin-note').val();

        $.ajax({
            url: `${API_URL}/api/admin/kyc-review`,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                kyc_id: currentKycId,
                action: 'approve',
                admin_note: adminNote
            }),
            beforeSend: function (xhr) { xhr.setRequestHeader('Authorization', 'Bearer ' + token); },
            success: function (res) {
                alert(res.message);
                $('#kycModal').modal('hide');
                loadKycList();
            },
            error: function (xhr) {
                alert("Lỗi: " + xhr.responseJSON.message);
            }
        });
    });

    // Từ chối KYC
    $('#btn-reject-kyc').on('click', function () {
        const adminNote = $('#modal-admin-note').val();

        if (!adminNote) {
            alert('Vui lòng nhập lý do từ chối!');
            return;
        }

        if (!confirm('Xác nhận TỪ CHỐI KYC này?')) return;

        $.ajax({
            url: `${API_URL}/api/admin/kyc-review`,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                kyc_id: currentKycId,
                action: 'reject',
                admin_note: adminNote
            }),
            beforeSend: function (xhr) { xhr.setRequestHeader('Authorization', 'Bearer ' + token); },
            success: function (res) {
                alert(res.message);
                $('#kycModal').modal('hide');
                loadKycList();
            },
            error: function (xhr) {
                alert("Lỗi: " + xhr.responseJSON.message);
            }
        });
    });

    // Tải dữ liệu lần đầu
    loadKycList();
});