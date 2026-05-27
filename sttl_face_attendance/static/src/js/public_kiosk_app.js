/* @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import attendanceApp from "@hr_attendance/public_kiosk/public_kiosk_app";
import { rpc } from "@web/core/network/rpc";

const MODEL_URL = '/sttl_face_attendance/static/face-api/weights/';
const MATCH_THRESHOLD = 0.38;

patch(attendanceApp.kioskAttendanceApp.prototype, {
    setup() {
        super.setup();
    },

    initiateFaceAttendance: async function () {
        await this.setupCamera();
    },

    async onManualSelection(employeeId, enteredPin) {
        await this.setupCamera(employeeId, enteredPin);
    },

    async setupCamera(employeeId) {
        return new Promise(async (resolve) => {
            const overlay = this._createOverlay();
            let video;
            try {
                this._setCameraStatus(_t("Loading face recognition..."));
                await Promise.all([
                    faceapi.nets.ssdMobilenetv1.load(MODEL_URL),
                    faceapi.nets.faceLandmark68Net.load(MODEL_URL),
                    faceapi.nets.faceRecognitionNet.load(MODEL_URL),
                ]);

                const stream = await navigator.mediaDevices.getUserMedia({
                    video: {
                        width: { ideal: 1280 },
                        height: { ideal: 720 },
                        facingMode: 'user',
                    },
                });
                video = this._setupVideoStream(stream, overlay);
                this._setCameraStatus(_t("Preparing enrolled faces..."));

                const employeeDetails = await rpc('/employee/images', {
                    token: this.props.token,
                    employee_id: employeeId,
                });
                const faceMatcher = this._buildFaceMatcher(employeeDetails);
                if (!faceMatcher) {
                    this._setCameraStatus(_t("No enrolled face descriptor found. Recapture the employee face from the employee form."));
                    this._disableCaptureButton();
                    this._addEventListeners(video, overlay, resolve, null);
                    return;
                }

                this._setCameraStatus(_t("Position one face, then click Capture."));
                this._addEventListeners(video, overlay, resolve, faceMatcher);
            } catch (error) {
                console.error(error);
                this.displayNotification(_t("Unable to access the camera"));
                this._handleError(video, overlay, resolve);
            }
        });
    },

    _createOverlay() {
        const overlay = document.createElement('div');
        overlay.id = 'camera_overlay';
        document.body.appendChild(overlay);
        return overlay;
    },

    _setupVideoStream(stream, overlay) {
        const camDiv = document.createElement('div');
        camDiv.id = 'cam-div';
        overlay.appendChild(camDiv);

        const header = document.createElement('div');
        header.id = 'camera-header';
        camDiv.appendChild(header);

        const title = document.createElement('div');
        title.id = 'camera-title';
        title.textContent = _t('Face Attendance');
        header.appendChild(title);

        const subtitle = document.createElement('div');
        subtitle.id = 'camera-subtitle';
        subtitle.textContent = _t('Odoo kiosk verification');
        header.appendChild(subtitle);

        const frame = document.createElement('div');
        frame.id = 'camera-frame';
        camDiv.appendChild(frame);

        const video = document.createElement('video');
        video.id = 'camera-stream';
        video.autoplay = true;
        video.playsInline = true;
        frame.appendChild(video);

        const resultBox = document.createElement('div');
        resultBox.id = 'camera-result';
        resultBox.innerHTML = `
            <div id="camera-result-icon">
                <i class="fa fa-check"></i>
            </div>
            <div id="camera-result-title"></div>
            <div id="camera-result-subtitle"></div>
        `;
        camDiv.appendChild(resultBox);

        const status = document.createElement('div');
        status.id = 'camera-status';
        status.textContent = _t('Starting camera...');
        camDiv.appendChild(status);

        const controls = document.createElement('div');
        controls.id = 'camera-controls';
        camDiv.appendChild(controls);

        const captureButton = document.createElement('button');
        captureButton.id = 'capture-button';
        captureButton.type = 'button';
        captureButton.className = 'btn btn-primary';
        captureButton.textContent = _t('Capture');
        controls.appendChild(captureButton);

        const closeButton = document.createElement('button');
        closeButton.id = 'close-button';
        closeButton.type = 'button';
        closeButton.className = 'btn btn-secondary';
        closeButton.textContent = _t('Close');
        controls.appendChild(closeButton);

        video.srcObject = stream;
        video.play();

        return video;
    },

    _addEventListeners(video, overlay, resolve, faceMatcher) {
        const captureButton = document.getElementById('capture-button');

        captureButton.addEventListener('click', async () => {
            if (!faceMatcher) {
                this._setCameraStatus(_t("Please recapture the employee face before attendance capture."));
                return;
            }
            captureButton.disabled = true;
            captureButton.innerHTML = `<span class="o_face_spinner me-2"></span>${_t("Checking")}`;
            this._setCameraStatus(_t("Checking captured face..."));
            try {
                const matchingEmployeeId = await this._captureMatchingEmployee(video, faceMatcher);
                if (matchingEmployeeId) {
                    await this._handleEmployeeDetected(matchingEmployeeId, video, overlay, resolve);
                } else {
                    this._setCameraStatus(_t("Face does not match any enrolled employee."));
                    this.displayNotification(_t("No matching employee found."));
                    this._resetCaptureButton();
                }
            } catch (error) {
                console.error(error);
                this._setCameraStatus(_t("Face detection failed. Please try again."));
                this.displayNotification(_t("Face detection failed."));
                this._resetCaptureButton();
            }
        });

        document.getElementById('close-button').addEventListener('click', () => {
            this._handleError(video, overlay, resolve);
        });
    },

    async _captureMatchingEmployee(video, faceMatcher) {
        const faceDetection = await this._detectBestFace(video, true);
        if (!faceDetection) {
            return null;
        }

        const bestMatch = faceMatcher.findBestMatch(faceDetection.descriptor);
        if (bestMatch.label === 'unknown' || bestMatch.distance > MATCH_THRESHOLD) {
            return null;
        }
        return Number(bestMatch.label);
    },

    _buildFaceMatcher(employeeDetails) {
        const labeledDescriptors = [];
        for (const { employee_id, face_descriptor } of employeeDetails) {
            const storedDescriptor = this._parseStoredDescriptor(face_descriptor);
            if (!storedDescriptor) {
                continue;
            }
            labeledDescriptors.push(
                new faceapi.LabeledFaceDescriptors(String(employee_id), [storedDescriptor])
            );
        }
        if (!labeledDescriptors.length) {
            return null;
        }
        return new faceapi.FaceMatcher(labeledDescriptors, MATCH_THRESHOLD);
    },

    _parseStoredDescriptor(faceDescriptor) {
        if (!faceDescriptor) {
            return null;
        }
        try {
            const values = JSON.parse(faceDescriptor);
            if (!Array.isArray(values) || values.length !== 128) {
                return null;
            }
            return new Float32Array(values);
        } catch {
            return null;
        }
    },

    async _detectBestFace(input, requireSingleFace = false) {
        const detections = await faceapi.detectAllFaces(input, new faceapi.SsdMobilenetv1Options({ minConfidence: 0.7 }))
            .withFaceLandmarks()
            .withFaceDescriptors();

        if (!detections.length) {
            this._setCameraStatus(_t("No clear face detected. Face the camera and try again."));
            return null;
        }
        if (requireSingleFace && detections.length > 1) {
            this._setCameraStatus(_t("Multiple faces detected. Keep only one face in the camera."));
            return null;
        }
        return detections.reduce((best, detection) => {
            const bestArea = best.detection.box.width * best.detection.box.height;
            const detectionArea = detection.detection.box.width * detection.detection.box.height;
            return detectionArea > bestArea ? detection : best;
        });
    },

    async _handleEmployeeDetected(employeeId, video, overlay, resolve) {
        this.employee_id = employeeId;
        this._stopStream(video);
        this._setCameraStatus(_t("Recording attendance..."));

        const result = await this.makeRpcWithGeolocation('face_selection', {
            token: this.props.token,
            employee_id: employeeId,
        });
        if (result && result.attendance) {
            this.employeeData = result;
            const checkedOut = Boolean(result.attendance.check_out);
            this._showAttendanceResult(
                checkedOut ? _t("Checked Out") : _t("Checked In"),
                result.employee_name || _t("Attendance recorded")
            );
            await this._delay(1100);
            overlay.remove();
            this.switchDisplay('greet');
            resolve(true);
        } else {
            this.displayNotification(_t("Face matched, but attendance could not be recorded."));
            this._setCameraStatus(_t("Attendance could not be recorded. Please try again."));
            this._resetCaptureButton();
            resolve(false);
        }
    },

    _handleError(video, overlay, resolve) {
        if (video) {
            this._stopStream(video);
        }
        if (overlay && document.body.contains(overlay)) {
            overlay.remove();
        }
        resolve(false);
    },

    _setCameraStatus(message) {
        const status = document.getElementById('camera-status');
        if (status) {
            status.textContent = message;
        }
    },

    _showAttendanceResult(title, subtitle) {
        const dialog = document.getElementById('cam-div');
        const resultBox = document.getElementById('camera-result');
        const resultTitle = document.getElementById('camera-result-title');
        const resultSubtitle = document.getElementById('camera-result-subtitle');
        const captureButton = document.getElementById('capture-button');
        const closeButton = document.getElementById('close-button');

        if (dialog) {
            dialog.classList.add('o_attendance_recorded');
        }
        if (resultTitle) {
            resultTitle.textContent = title;
        }
        if (resultSubtitle) {
            resultSubtitle.textContent = subtitle;
        }
        if (resultBox) {
            resultBox.classList.add('show');
        }
        if (captureButton) {
            captureButton.disabled = true;
            captureButton.innerHTML = `<i class="fa fa-check me-2"></i>${title}`;
        }
        if (closeButton) {
            closeButton.disabled = true;
        }
        this._setCameraStatus(_t("Attendance recorded successfully."));
    },

    _resetCaptureButton() {
        const captureButton = document.getElementById('capture-button');
        if (captureButton) {
            captureButton.disabled = false;
            captureButton.textContent = _t("Capture");
        }
    },

    _delay(ms) {
        return new Promise((resolve) => window.setTimeout(resolve, ms));
    },

    _disableCaptureButton() {
        const captureButton = document.getElementById('capture-button');
        if (captureButton) {
            captureButton.disabled = true;
        }
    },

    _stopStream(video) {
        if (video.srcObject) {
            video.srcObject.getTracks().forEach(track => track.stop());
            video.srcObject = null;
        }
    },
});
