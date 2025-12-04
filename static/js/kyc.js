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

        // Validate
        if (!formData.get('id_front').name || !formData.get('id_back').name || !formData.get('selfie').name || !formData.get('paper').name) {
            alert('Vui lòng tải lên đủ 4 ảnh theo yêu cầu!');
            return;
        }

        $('#btn-submit-kyc').prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Đang tải lên...');

        $.ajax({
            url: `${API_URL}/api/user/submit-kyc`,
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function (res) {
                alert('✅ Gửi xác minh thành công! Chúng tôi sẽ xét duyệt trong 24h.');
                location.reload();
            },
            error: function (xhr) {
                alert('❌ Lỗi: ' + xhr.responseJSON.message);
                $('#btn-submit-kyc').prop('disabled', false).html('<i class="fa fa-check-circle"></i> Gửi Xác Minh');
            }
        });
    });
});