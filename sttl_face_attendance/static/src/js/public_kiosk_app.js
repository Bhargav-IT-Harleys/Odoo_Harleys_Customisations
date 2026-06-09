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
        this.faceAttendanceMatchedEmployeeId = null;
        this.faceAttendanceShiftTimer = null;
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
        this.faceAttendanceMatchedEmployeeId = null;
        this._clearFaceAttendanceShiftTimer();

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
        let setupStage = "models";
        try {
            this._setCameraStatus(_t("Loading face recognition..."));
            await Promise.all([
                faceapi.nets.tinyFaceDetector.load(MODEL_URL),
                faceapi.nets.faceLandmark68Net.load(MODEL_URL),
                faceapi.nets.faceRecognitionNet.load(MODEL_URL),
            ]);

            setupStage = "camera";
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                const error = new Error("Camera API is unavailable.");
                error.name = "CameraApiUnavailable";
                throw error;
            }
            const stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                    facingMode: "user",
                },
            });
            video = this._setupVideoStream(stream, overlay);
            this._setCameraStatus(_t("Preparing enrolled faces..."));

            setupStage = "attendance";
            const employeeDetails = await rpc("/employee/images", {
                token: this.props.token,
                employee_id: employeeId,
            });
            if (!employeeDetails.length) {
                this._setCameraStatus(
                    _t("No employee face is enrolled. Capture the employee face first.")
                );
                this._showFaceScanButton();
                this._setFaceScanButtonDisabled(true);
                this._setActionButtonsDisabled(true);
            } else {
                const selectedEmployee = this._getSelectedEmployee(employeeId, employeeDetails);
                if (selectedEmployee) {
                    this.faceAttendanceMatchedEmployeeId = selectedEmployee.employee_id;
                    this._showAttendanceActions(selectedEmployee);
                    this._setCameraStatus(this._getActionPrompt(selectedEmployee));
                    this._scheduleShiftActionUpdate(selectedEmployee);
                } else {
                    this._showFaceScanButton();
                    this._setCameraStatus(_t("Position one face, then click Identify Face."));
                }
            }
            this._addEventListeners(video, overlay, resolve, employeeDetails);
        } catch (error) {
            console.error(error);
            this.displayNotification(this._getFaceSetupErrorMessage(error, setupStage));
            this._handleError(video, overlay, resolve);
        }
    },

    _getFaceSetupErrorMessage(error, setupStage) {
        if (setupStage === "models") {
            return _t("Unable to load the face recognition models.");
        }
        if (setupStage === "attendance") {
            return _t("Unable to load employee attendance data.");
        }
        if (error && error.name === "CameraApiUnavailable") {
            return _t("Camera access requires HTTPS or localhost.");
        }
        if (error && error.name === "NotAllowedError") {
            return _t("Camera permission was denied.");
        }
        if (error && error.name === "NotFoundError") {
            return _t("No camera was found on this device.");
        }
        if (error && error.name === "NotReadableError") {
            return _t("The camera is already in use or unavailable.");
        }
        return _t("Unable to access the camera.");
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
                "scan-face-button",
                "btn btn-primary",
                _t("Identify Face"),
                "fa-camera"
            )
        );
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
        document.getElementById("scan-face-button").addEventListener("click", () => {
            this._identifyEmployeeForAction(video, employeeDetails);
        });
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

    async _identifyEmployeeForAction(video, employeeDetails) {
        if (this.faceAttendanceProcessing) {
            return;
        }

        this.faceAttendanceProcessing = true;
        this._setFaceScanButtonDisabled(true);
        this._setCameraStatus(_t("Identifying employee face..."));

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
                this._showFaceScanButton();
                this._resetActionButtons();
                return;
            }

            const matchingEmployee = this._getEmployeeDetails(
                matchingEmployeeId,
                employeeDetails
            );
            if (!matchingEmployee) {
                this._setCameraStatus(_t("Face verification failed. Please try again."));
                this._showFaceScanButton();
                this._resetActionButtons();
                return;
            }
            this.faceAttendanceMatchedEmployeeId = matchingEmployeeId;
            this._showAttendanceActions(matchingEmployee);
            this._setCameraStatus(this._getActionPrompt(matchingEmployee));
            this._scheduleShiftActionUpdate(matchingEmployee);
            this._resetActionButtons();
        } catch (error) {
            console.error(error);
            this._setCameraStatus(_t("Face verification failed. Please try again."));
            this.displayNotification(_t("Face verification failed."));
            this._showFaceScanButton();
            this._resetActionButtons();
        }
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
        this._setCameraStatus(
            attendanceAction === "check_in"
                ? _t("Verifying face for Check In...")
                : _t("Verifying face for Check Out...")
        );

        try {
            const employeeDetailsForMatch = this.faceAttendanceMatchedEmployeeId
                ? employeeDetails.filter(
                    ({ employee_id }) =>
                        String(employee_id) === String(this.faceAttendanceMatchedEmployeeId)
                )
                : employeeDetails;
            const matchingEmployeeId = await this._captureMatchingEmployee(
                video,
                employeeDetailsForMatch
            );
            if (!matchingEmployeeId) {
                this._setCameraStatus(
                    _t("Face does not match any enrolled employee. Please try again.")
                );
                this.displayNotification(_t("No matching employee found."));
                this._resetActionButtons();
                return;
            }

            const matchingEmployee = this._getEmployeeDetails(matchingEmployeeId, employeeDetails);
            if (!matchingEmployee) {
                this._setCameraStatus(_t("Face verification failed. Please try again."));
                this._resetActionButtons();
                return;
            }
            const availableActions = this._getAvailableAttendanceActions(matchingEmployee);
            this.faceAttendanceMatchedEmployeeId = matchingEmployeeId;
            this._showAttendanceActions(matchingEmployee);
            if (!availableActions.includes(attendanceAction)) {
                this._setCameraStatus(this._getActionPrompt(matchingEmployee));
                this.displayNotification(this._getActionPrompt(matchingEmployee));
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
                this._clearFaceAttendanceShiftTimer();
                this._stopStream(video);
                if (document.body.contains(overlay)) {
                    overlay.remove();
                }
                this.employeeData = result;
                this.switchDisplay("greet");
                resolve(true);
                return;
            }

            if (result && result.attendance_state) {
                this._showAttendanceActions(result);
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
        this._setFaceScanButtonDisabled(false);
    },

    _setActionButtonsDisabled(disabled) {
        for (const id of ["check-in-button", "check-out-button"]) {
            const button = document.getElementById(id);
            if (button) {
                button.disabled = disabled;
            }
        }
    },

    _setFaceScanButtonDisabled(disabled) {
        const button = document.getElementById("scan-face-button");
        if (button) {
            button.disabled = disabled;
        }
    },

    _showFaceScanButton() {
        this._setButtonHidden("scan-face-button", false);
        this._setButtonHidden("check-in-button", true);
        this._setButtonHidden("check-out-button", true);
    },

    _showAttendanceActions(employeeDetails) {
        const availableActions = this._getAvailableAttendanceActions(employeeDetails);
        this._setButtonHidden("scan-face-button", true);
        this._setButtonHidden("check-in-button", !availableActions.includes("check_in"));
        this._setButtonHidden("check-out-button", !availableActions.includes("check_out"));
    },

    _setButtonHidden(id, hidden) {
        const button = document.getElementById(id);
        if (button) {
            button.classList.toggle("d-none", hidden);
        }
    },

    _getSelectedEmployee(employeeId, employeeDetails) {
        if (employeeId) {
            return this._getEmployeeDetails(employeeId, employeeDetails);
        }
        return employeeDetails.length === 1 ? employeeDetails[0] : null;
    },

    _getEmployeeDetails(employeeId, employeeDetails) {
        return employeeDetails.find(
            ({ employee_id }) => String(employee_id) === String(employeeId)
        );
    },

    _getAvailableAttendanceActions(employeeDetails) {
        if (employeeDetails.attendance_state !== "checked_in") {
            return ["check_in"];
        }
        return employeeDetails.shift_expired
            ? ["check_in"]
            : ["check_out"];
    },

    _getActionPrompt(employeeDetails) {
        if (employeeDetails.attendance_state !== "checked_in") {
            return _t("Face matched. Please use Check In.");
        }
        return employeeDetails.shift_expired
            ? _t("Shift duration exceeded. Please use Check In.")
            : _t("Face matched. Please use Check Out.");
    },

    _scheduleShiftActionUpdate(employeeDetails) {
        this._clearFaceAttendanceShiftTimer();
        if (
            employeeDetails.attendance_state !== "checked_in"
            || employeeDetails.shift_expired
            || !employeeDetails.shift_seconds_remaining
        ) {
            return;
        }

        const delay = Math.max(0, employeeDetails.shift_seconds_remaining * 1000);
        this.faceAttendanceShiftTimer = setTimeout(() => {
            if (
                String(this.faceAttendanceMatchedEmployeeId)
                !== String(employeeDetails.employee_id)
            ) {
                return;
            }
            employeeDetails.shift_expired = true;
            employeeDetails.shift_seconds_remaining = 0;
            this._showAttendanceActions(employeeDetails);
            this._setCameraStatus(this._getActionPrompt(employeeDetails));
        }, delay);
    },

    _clearFaceAttendanceShiftTimer() {
        if (this.faceAttendanceShiftTimer) {
            clearTimeout(this.faceAttendanceShiftTimer);
            this.faceAttendanceShiftTimer = null;
        }
    },

    _setCameraStatus(message) {
        const status = document.getElementById("camera-status");
        if (status) {
            status.textContent = message;
        }
    },

    _handleError(video, overlay, resolve) {
        this._clearFaceAttendanceShiftTimer();
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
