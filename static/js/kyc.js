$(document).ready(function () {
    
    // Kiểm tra trạng thái KYC hiện tại
    $.ajax({
        url: `${API_URL}/api/user/kyc-status`,
        type: 'GET',
        success: function (res) {
            if (res.kyc) {
                const kyc = res.kyc;
                let statusClass = 'pending';
                let statusText = '⏳ Đang chờ duyệt';
                let statusIcon = 'fa-clock-o';

                if (kyc.status === 'approved') {
                    statusClass = 'approved';
                    statusText = '✅ Đã xác minh thành công';
                    statusIcon = 'fa-check-circle';
                    $('#kyc-form').hide(); 
                    $('#kyc-status-box').append('<div class="alert alert-success">Tài khoản của bạn đã được xác minh!</div>');
                
                } else if (kyc.status === 'pending') {
                    statusClass = 'pending';
                    statusText = '⏳ Đang chờ duyệt';
                
                    $('#kyc-form :input').prop('disabled', true);
                    $('#btn-submit-kyc').text('Đang chờ xét duyệt...').prop('disabled', true);
                
                } else if (kyc.status === 'rejected') {
                    statusClass = 'rejected';
                    statusText = '❌ Bị từ chối - Hãy gửi lại';
                }

                $('#kyc-status-box').show().html(`
                    <div class="kyc-status ${statusClass}">
                        <h4><i class="fa ${statusIcon}"></i> ${statusText}</h4>
                        <p><strong>Ngày gửi:</strong> ${kyc.submitted_at}</p>
                        ${kyc.admin_note ? `<p><strong>Ghi chú:</strong> ${escapeHTML(kyc.admin_note)}</p>` : ''}
                    </div>
                `);
            }
        }
    });

    // Preview ảnh khi chọn
    $('#id_front').on('change', function () {
        const file = this.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function (e) {
                $('#preview_front').attr('src', e.target.result).show();
            };
            reader.readAsDataURL(file);
        }
    });

    $('#id_back').on('change', function () {
        const file = this.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function (e) {
                $('#preview_back').attr('src', e.target.result).show();
            };
            reader.readAsDataURL(file);
        }
    });

    $('#selfie').on('change', function () {
        const file = this.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function (e) {
                $('#preview_selfie').attr('src', e.target.result).show();
            };
            reader.readAsDataURL(file);
        }
    });

    $('#paper').on('change', function () {
        const file = this.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function (e) {
                $('#preview_paper').attr('src', e.target.result).show();
            };
            reader.readAsDataURL(file);
        }
    });

    // Submit form
    $('#kyc-form').on('submit', function (e) {
        e.preventDefault();

        const formData = new FormData(this);
        
        // 1. Validate có đủ file chưa
        if (!formData.get('id_front').name || !formData.get('id_back').name || !formData.get('selfie').name || !formData.get('paper').name) {
            alert('Vui lòng tải lên đủ 4 ảnh theo yêu cầu!');
            return;
        }

        // 2. Validate dung lượng file Client-side (Tránh gửi file quá nặng gây treo)
        let totalSize = 0;
        let isFileTooBig = false;
        const maxFileSize = 10 * 1024 * 1024; // 10MB mỗi file
        
        ['id_front', 'id_back', 'selfie', 'paper'].forEach(key => {
            let file = formData.get(key);
            if(file && file.size) {
                totalSize += file.size;
                if (file.size > maxFileSize) {
                    alert(`Ảnh ${key} quá lớn (>10MB). Vui lòng nén lại hoặc chọn ảnh khác.`);
                    isFileTooBig = true;
                }
            }
        });

        if (isFileTooBig) return;
        if (totalSize > 45 * 1024 * 1024) { // Tổng > 45MB
             alert('Tổng dung lượng các ảnh quá lớn. Vui lòng giảm dung lượng ảnh.');
             return;
        }

        // Bắt đầu hiệu ứng loading
        $('#btn-submit-kyc').prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Đang tải lên...');

        $.ajax({
            url: `${API_URL}/api/user/submit-kyc`,
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            timeout: 60000, // Thêm timeout 60 giây để tránh treo mãi
            success: function (res) {
                alert('✅ Gửi xác minh thành công! Chúng tôi sẽ xét duyệt trong 24h.');
                location.reload();
            },
            error: function (xhr, status, error) {
                // Reset nút bấm
                $('#btn-submit-kyc').prop('disabled', false).html('<i class="fa fa-paper-plane"></i> GỬI HỒ SƠ XÉT DUYỆT');

                // Xử lý thông báo lỗi an toàn hơn
                let msg = 'Có lỗi xảy ra, vui lòng thử lại.';
                
                if (xhr.responseJSON && xhr.responseJSON.message) {
                    // Trường hợp server trả về JSON lỗi (VD: thiếu file, lỗi logic)
                    msg = '❌ Lỗi: ' + xhr.responseJSON.message;
                } else if (xhr.status === 413) {
                    // Trường hợp file quá lớn server chặn (Nginx/Flask trả về HTML)
                    msg = '❌ Ảnh quá lớn! Server từ chối nhận. Vui lòng nén ảnh lại.';
                } else if (status === 'timeout') {
                    msg = '❌ Kết nối quá hạn (Timeout). Mạng chậm hoặc ảnh quá nặng.';
                } else {
                    // Các lỗi server 500, 502...
                    console.error(xhr.responseText); // Log ra console để debug
                    msg = `❌ Lỗi máy chủ (${xhr.status}). Vui lòng liên hệ Admin.`;
                }

                alert(msg);
            }
        });
    });
});