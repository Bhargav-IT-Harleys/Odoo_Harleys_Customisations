/* @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import attendanceApp from "@hr_attendance/public_kiosk/public_kiosk_app";
import { rpc } from "@web/core/network/rpc";

const MODEL_URL = "/sttl_face_attendance/static/face-api/weights/";
const MATCH_THRESHOLD = 0.45;
const ATTENDANCE_ACTIONS = ["check_in", "check_out"];

patch(attendanceApp.kioskAttendanceApp.prototype, {
    setup() {
        super.setup();
        this.faceAttendanceActive = false;
        this.faceAttendanceProcessing = false;
    },

    async initiateFaceAttendance() {
        await this.setupCamera();
    },

    async onManualSelection(employeeId, _enteredPin) {
        await this.setupCamera(employeeId);
    },

    async setupCamera(employeeId) {
        if (this.faceAttendanceActive) {
            return false;
        }
        this.faceAttendanceActive = true;
        this.faceAttendanceProcessing = false;

        try {
            return await new Promise((resolve) => {
                this._initializeFaceCamera(employeeId, resolve);
            });
        } finally {
            this.faceAttendanceActive = false;
        }
    },

    async _initializeFaceCamera(employeeId, resolve) {
        const overlay = this._createOverlay();
        let video;
        try {
            this._setCameraStatus(_t("Loading face recognition..."));
            await Promise.all([
                faceapi.nets.tinyFaceDetector.load(MODEL_URL),
                faceapi.nets.faceLandmark68Net.load(MODEL_URL),
                faceapi.nets.faceRecognitionNet.load(MODEL_URL),
            ]);

            const stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                    facingMode: "user",
                },
            });
            video = this._setupVideoStream(stream, overlay);
            this._setCameraStatus(_t("Preparing enrolled faces..."));

            const employeeDetails = await rpc("/employee/images", {
                token: this.props.token,
                employee_id: employeeId,
            });
            if (!employeeDetails.length) {
                this._setCameraStatus(
                    _t("No employee face is enrolled. Capture the employee face first.")
                );
                this._setActionButtonsDisabled(true);
            } else {
                this._setCameraStatus(
                    _t("Position one face, then choose Check In or Check Out.")
                );
            }
            this._addEventListeners(video, overlay, resolve, employeeDetails);
        } catch (error) {
            console.error(error);
            this.displayNotification(_t("Unable to access the camera."));
            this._handleError(video, overlay, resolve);
        }
    },

    _createOverlay() {
        const overlay = document.createElement("div");
        overlay.id = "camera_overlay";
        document.body.appendChild(overlay);
        return overlay;
    },

    _setupVideoStream(stream, overlay) {
        const camDiv = document.createElement("div");
        camDiv.id = "cam-div";
        overlay.appendChild(camDiv);

        const header = document.createElement("div");
        header.id = "camera-header";
        camDiv.appendChild(header);

        const title = document.createElement("div");
        title.id = "camera-title";
        title.textContent = _t("Face Attendance");
        header.appendChild(title);

        const subtitle = document.createElement("div");
        subtitle.id = "camera-subtitle";
        subtitle.textContent = _t("Choose an action after positioning your face");
        header.appendChild(subtitle);

        const frame = document.createElement("div");
        frame.id = "camera-frame";
        camDiv.appendChild(frame);

        const video = document.createElement("video");
        video.id = "camera-stream";
        video.autoplay = true;
        video.playsInline = true;
        frame.appendChild(video);

        const status = document.createElement("div");
        status.id = "camera-status";
        status.textContent = _t("Starting camera...");
        camDiv.appendChild(status);

        const controls = document.createElement("div");
        controls.id = "camera-controls";
        camDiv.appendChild(controls);

        controls.appendChild(
            this._createActionButton(
                "check-in-button",
                "btn btn-success",
                _t("Check In"),
                "fa-sign-in"
            )
        );
        controls.appendChild(
            this._createActionButton(
                "check-out-button",
                "btn btn-danger",
                _t("Check Out"),
                "fa-sign-out"
            )
        );

        const closeButton = document.createElement("button");
        closeButton.id = "close-button";
        closeButton.type = "button";
        closeButton.className = "btn btn-secondary";
        closeButton.textContent = _t("Close");
        controls.appendChild(closeButton);

        video.srcObject = stream;
        video.play();
        return video;
    },

    _createActionButton(id, className, label, icon) {
        const button = document.createElement("button");
        button.id = id;
        button.type = "button";
        button.className = className;

        const iconElement = document.createElement("i");
        iconElement.className = `fa ${icon} me-2`;
        button.appendChild(iconElement);
        button.appendChild(document.createTextNode(label));
        return button;
    },

    _addEventListeners(video, overlay, resolve, employeeDetails) {
        document.getElementById("check-in-button").addEventListener("click", () => {
            this._verifyAndRecord(
                "check_in",
                video,
                overlay,
                resolve,
                employeeDetails
            );
        });
        document.getElementById("check-out-button").addEventListener("click", () => {
            this._verifyAndRecord(
                "check_out",
                video,
                overlay,
                resolve,
                employeeDetails
            );
        });
        document.getElementById("close-button").addEventListener("click", () => {
            this._handleError(video, overlay, resolve);
        });
    },

    async _verifyAndRecord(attendanceAction, video, overlay, resolve, employeeDetails) {
        if (
            this.faceAttendanceProcessing ||
            !ATTENDANCE_ACTIONS.includes(attendanceAction)
        ) {
            return;
        }

        this.faceAttendanceProcessing = true;
        this._setActionButtonsDisabled(true);
        this._setCloseButtonDisabled(true);
        this._setCameraStatus(
            attendanceAction === "check_in"
                ? _t("Verifying face for Check In...")
                : _t("Verifying face for Check Out...")
        );

        try {
            const matchingEmployeeId = await this._captureMatchingEmployee(
                video,
                employeeDetails
            );
            if (!matchingEmployeeId) {
                this._setCameraStatus(
                    _t("Face does not match any enrolled employee. Please try again.")
                );
                this.displayNotification(_t("No matching employee found."));
                this._resetActionButtons();
                return;
            }

            await this._recordFaceAttendance(
                matchingEmployeeId,
                attendanceAction,
                video,
                overlay,
                resolve
            );
        } catch (error) {
            console.error(error);
            this._setCameraStatus(_t("Face verification failed. Please try again."));
            this.displayNotification(_t("Face verification failed."));
            this._resetActionButtons();
        }
    },

    async _captureMatchingEmployee(video, employeeDetails) {
        const faceDetection = await faceapi
            .detectSingleFace(video, new faceapi.TinyFaceDetectorOptions())
            .withFaceLandmarks()
            .withFaceDescriptor();

        if (!faceDetection) {
            this._setCameraStatus(_t("No clear face detected. Face the camera and try again."));
            return null;
        }

        return this._findMatchingEmployee(faceDetection, employeeDetails);
    },

    async _findMatchingEmployee(faceDetection, employeeDetails) {
        let closestEmployeeId = null;
        let closestDistance = MATCH_THRESHOLD;

        for (const { employee_id, image } of employeeDetails) {
            if (!image) {
                continue;
            }

            try {
                const blob = this._base64ToBlob(image, "image/png");
                const referenceImage = await faceapi.bufferToImage(blob);
                const referenceDescriptor = await faceapi
                    .detectSingleFace(
                        referenceImage,
                        new faceapi.TinyFaceDetectorOptions()
                    )
                    .withFaceLandmarks()
                    .withFaceDescriptor();

                if (!referenceDescriptor) {
                    continue;
                }
                const distance = faceapi.euclideanDistance(
                    faceDetection.descriptor,
                    referenceDescriptor.descriptor
                );
                if (distance < closestDistance) {
                    closestDistance = distance;
                    closestEmployeeId = employee_id;
                }
            } catch (error) {
                console.debug("Unable to compare an enrolled employee face.", error);
            }
        }
        return closestEmployeeId;
    },

    async _recordFaceAttendance(
        employeeId,
        attendanceAction,
        video,
        overlay,
        resolve
    ) {
        this.employee_id = employeeId;
        this._setCameraStatus(_t("Face matched. Recording attendance..."));

        try {
            const result = await this.makeRpcWithGeolocation("face_selection", {
                token: this.props.token,
                employee_id: employeeId,
                attendance_action: attendanceAction,
            });
            if (result && result.attendance) {
                this._stopStream(video);
                if (document.body.contains(overlay)) {
                    overlay.remove();
                }
                this.employeeData = result;
                this.switchDisplay("greet");
                resolve(true);
                return;
            }

            this._setCameraStatus(this._getAttendanceErrorMessage(result));
            this.displayNotification(this._getAttendanceErrorMessage(result));
            this._resetActionButtons();
        } catch (error) {
            console.error(error);
            this._setCameraStatus(_t("Attendance could not be recorded. Please try again."));
            this.displayNotification(_t("Attendance could not be recorded."));
            this._resetActionButtons();
        }
    },

    _getAttendanceErrorMessage(result) {
        if (result && result.error === "already_checked_in") {
            return _t("This employee is already checked in.");
        }
        if (result && result.error === "already_checked_out") {
            return _t("This employee is already checked out.");
        }
        if (result && result.error === "invalid_action") {
            return _t("Invalid attendance action.");
        }
        return _t("Face matched, but attendance could not be recorded.");
    },

    _resetActionButtons() {
        this.faceAttendanceProcessing = false;
        this._setActionButtonsDisabled(false);
        this._setCloseButtonDisabled(false);
    },

    _setActionButtonsDisabled(disabled) {
        for (const id of ["check-in-button", "check-out-button"]) {
            const button = document.getElementById(id);
            if (button) {
                button.disabled = disabled;
            }
        }
    },

    _setCloseButtonDisabled(disabled) {
        const closeButton = document.getElementById("close-button");
        if (closeButton) {
            closeButton.disabled = disabled;
        }
    },

    _setCameraStatus(message) {
        const status = document.getElementById("camera-status");
        if (status) {
            status.textContent = message;
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

    _stopStream(video) {
        if (video.srcObject) {
            video.srcObject.getTracks().forEach((track) => track.stop());
            video.srcObject = null;
        }
    },

    _base64ToBlob(base64, mimeType) {
        const byteCharacters = atob(base64.split(",")[1] || base64);
        const byteArrays = [];

        for (let offset = 0; offset < byteCharacters.length; offset += 512) {
            const slice = byteCharacters.slice(offset, offset + 512);
            const byteArray = new Uint8Array(
                [...slice].map((character) => character.charCodeAt(0))
            );
            byteArrays.push(byteArray);
        }

        return new Blob(byteArrays, { type: mimeType });
    },
});
