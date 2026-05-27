/* @odoo-module */

import { Component, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ensureJQuery } from '@web/core/ensure_jquery';

const MODEL_URL = '/sttl_face_attendance/static/face-api/weights/';

class CaptureEmployeeImage extends Component {
    static template = "CaptureEmployeeImage";

    setup() {
        super.setup();
        this.employee_id = this.props.action.params.employee_id || this.props.action.params.active_id;
        this.orm = useService("orm");
        this.action = useService("action");
        try {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                alert("Unable to access the camera");
                this.env.config.historyBack();
            } else {
                onMounted(async () => {
                    await ensureJQuery();
                    this._bind_events();
                    try {
                        this._set_status("Loading face recognition models...");
                        await this._load_models();
                        this._set_status("Starting camera...");
                        await this._start_video_stream();
                        this._set_status("Camera ready. Position one clear face and capture.");
                    } catch (error) {
                        console.error(error);
                        this._set_status("Unable to start face capture. Please refresh and allow camera access.");
                    }
                })
            }
        }
        catch (error) {
            console.log(error);
        }
    }

    async _load_models() {
        if (!window.faceapi) {
            throw new Error("Face recognition library is not loaded.");
        }
        await Promise.all([
            faceapi.nets.ssdMobilenetv1.load(MODEL_URL),
            faceapi.nets.faceLandmark68Net.load(MODEL_URL),
            faceapi.nets.faceRecognitionNet.load(MODEL_URL),
        ]);
    }

    async _start_video_stream() {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                width: { ideal: 1280 },
                height: { ideal: 720 },
                facingMode: 'user',
            },
        });
        const video = document.getElementById('video');
        video.srcObject = stream;
        await video.play();
        await this._wait_for_video(video);
    }

    _bind_events() {
        $('#btn-close').on('click', this._on_close.bind(this));
        $('#btn-click').on('click', this._on_capture.bind(this));
        $('#btn-close-sub').on('click', this._on_close.bind(this));
    }

    async _on_capture() {
        try {
            const self = this;

            var video = document.getElementById('video');
            var canvas = document.getElementById('canvas');
            var context = canvas.getContext('2d');
            var captureButton = document.getElementById('btn-click');
            captureButton.disabled = true;
            this._set_status("Detecting face...");

            const faceDetection = await this._detect_registered_face(video);
            if (!faceDetection) {
                captureButton.disabled = false;
                return;
            }

            const targetWidth = 320;
            const targetHeight = 240;

            canvas.width = targetWidth;
            canvas.height = targetHeight;

            context.drawImage(video, 0, 0, targetWidth, targetHeight);

            var imageData = canvas.toDataURL('image/png');
            var faceDescriptor = JSON.stringify(Array.from(faceDetection.descriptor));

            this._set_status("Saving employee face...");
            this.orm.call('hr.employee', 'register_face',[this.employee_id, imageData, faceDescriptor])
            .then(function (result) {
                self._on_close();
            })
            .catch((error) => {
                console.error(error);
                captureButton.disabled = false;
                this._set_status("Unable to save face data. Please try again.");
            });
        } catch (error) {
            console.error(error);
            const captureButton = document.getElementById('btn-click');
            if (captureButton) {
                captureButton.disabled = false;
            }
            this._set_status(`Face capture failed: ${error.message || error}`);
        }
    }

    async _detect_registered_face(video) {
        if (!video || !video.videoWidth || !video.videoHeight) {
            this._set_status("Camera is not ready yet. Please wait a moment.");
            return null;
        }

        const detections = await faceapi.detectAllFaces(video, new faceapi.SsdMobilenetv1Options({ minConfidence: 0.7 }))
            .withFaceLandmarks()
            .withFaceDescriptors();

        if (!detections.length) {
            this._set_status("No clear face detected. Face the camera and try again.");
            return null;
        }
        if (detections.length > 1) {
            this._set_status("Multiple faces detected. Capture only one employee.");
            return null;
        }
        return detections[0];
    }

    _wait_for_video(video) {
        return new Promise((resolve, reject) => {
            if (video.videoWidth && video.videoHeight) {
                resolve();
                return;
            }
            const timeout = window.setTimeout(() => {
                reject(new Error("Camera video did not become ready."));
            }, 8000);
            video.onloadedmetadata = () => {
                window.clearTimeout(timeout);
                resolve();
            };
        });
    }

    _set_status(message) {
        const status = document.getElementById('capture-status');
        if (status) {
            status.textContent = message;
        }
    }

    _stop_stream() {
        var video = document.getElementById('video');
        if (video && video.srcObject) {
            let tracks = video.srcObject.getTracks();
            tracks.forEach(track => track.stop());
            video.srcObject = null;
        }
    }

    _on_close() {
        this._stop_stream();
        this.env.config.historyBack();
    }
    
}

registry.category("actions").add("new_employee_image", CaptureEmployeeImage);
