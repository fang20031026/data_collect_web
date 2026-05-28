#!/usr/bin/env python3
"""
Serve a small web page for viewing a camera feed.

Default mode uses the browser's camera API, which works on localhost without
extra Python packages. Use --server-camera to stream /dev/video0 through ffmpeg.
"""

from __future__ import annotations

import argparse
from email.parser import BytesParser
from email.policy import default as email_policy
import html
import json
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


CLIENT_CAMERA_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Camera Preview</title>
  <style>
    :root {
      color-scheme: dark;
      font-family: Arial, Helvetica, sans-serif;
      background: #101316;
      color: #f1f5f9;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr auto;
    }
    header, footer {
      padding: 14px 18px;
      background: #171c21;
      border-bottom: 1px solid #2b333b;
    }
    footer {
      border-top: 1px solid #2b333b;
      border-bottom: 0;
      color: #a8b3bd;
      font-size: 14px;
    }
    main {
      display: grid;
      place-items: center;
      padding: 18px;
    }
    .stage {
      width: min(100%, 1280px);
      aspect-ratio: 16 / 9;
      display: grid;
      place-items: center;
    }
    video, canvas {
      width: 100%;
      height: 100%;
      background: #050607;
      border: 1px solid #303943;
      border-radius: 8px;
      object-fit: contain;
    }
    .hidden { display: none !important; }
    .mode-group {
      display: inline-flex;
      gap: 8px;
    }
    .mode-button.active {
      background: #2f7d52;
      border-color: #45a56e;
      color: #f7fff9;
    }
    button {
      border: 1px solid #3d4854;
      border-radius: 8px;
      background: #e7eef7;
      color: #11161b;
      font-size: 16px;
      padding: 10px 14px;
      cursor: pointer;
    }
    button:disabled {
      cursor: not-allowed;
      opacity: 0.55;
    }
    button.toggle {
      min-width: 116px;
      background: #2f7d52;
      border-color: #45a56e;
      color: #f7fff9;
    }
    button.toggle.manual {
      background: #6b7280;
      border-color: #8b95a1;
    }
    input, select {
      min-width: min(420px, 100%);
      border: 1px solid #3d4854;
      border-radius: 8px;
      background: #0e1216;
      color: #f1f5f9;
      font-size: 15px;
      padding: 10px 12px;
    }
    a {
      color: #9bd2ff;
      text-decoration: none;
    }
    .panel {
      width: min(100%, 1280px);
      display: grid;
      gap: 10px;
      margin: 12px 0 0;
    }
    .row {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }
    .label {
      color: #a8b3bd;
      min-width: 82px;
    }
    .multi-row {
      display: grid;
      grid-template-columns: 70px minmax(180px, 420px) 104px minmax(180px, 1fr);
      gap: 10px;
      align-items: center;
      width: 100%;
    }
    .multi-role {
      font-weight: 700;
      color: #f1f5f9;
    }
    .step {
      border-top: 1px solid #2b333b;
      padding-top: 10px;
    }
    .step:first-child {
      border-top: 0;
      padding-top: 0;
    }
    .step-title {
      color: #f1f5f9;
      font-weight: 700;
      min-width: 120px;
    }
    .ok { color: #7ddf9f; }
    .warn { color: #ffd166; }
    .bad { color: #ff8a8a; }
    .bar {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }
    #status, #resolution, #recordingTime, #savePath { color: #a8b3bd; }
    #status.ok { color: #7ddf9f; }
    #status.warn { color: #ffd166; }
    #status.bad { color: #ff8a8a; }
    .multi-stage {
      width: min(100%, 1440px);
      aspect-ratio: 16 / 9;
      display: grid;
      grid-template-columns: 2fr 1fr;
      grid-template-rows: 1fr 1fr;
      gap: 10px;
    }
    .multi-view {
      position: relative;
      min-width: 0;
      min-height: 0;
    }
    .multi-head { grid-column: 1; grid-row: 1 / span 2; }
    .multi-left { grid-column: 2; grid-row: 1; }
    .multi-right { grid-column: 2; grid-row: 2; }
    .view-label {
      position: absolute;
      left: 10px;
      top: 10px;
      padding: 4px 8px;
      background: rgba(0, 0, 0, 0.62);
      border-radius: 8px;
      color: #f1f5f9;
      font-size: 14px;
      pointer-events: none;
    }
    .source-video {
      position: fixed;
      width: 1px;
      height: 1px;
      left: -10px;
      top: -10px;
      opacity: 0;
      pointer-events: none;
    }
    @media (max-width: 760px) {
      .multi-row {
        grid-template-columns: 1fr;
      }
      .multi-stage {
        aspect-ratio: auto;
        grid-template-columns: 1fr;
        grid-template-rows: auto auto auto;
      }
      .multi-head, .multi-left, .multi-right {
        grid-column: 1;
        grid-row: auto;
      }
      .multi-view {
        aspect-ratio: 16 / 9;
      }
    }
  </style>
</head>
<body>
  <header>
    <div class="bar">
      <button id="shutdown" type="button">退出程序</button>
      <span id="status">等待授权</span>
      <span id="resolution"></span>
      <span id="recordingTime"></span>
      <a id="download" hidden>下载备份</a>
    </div>
    <div class="panel">
      <div class="row step">
        <span class="step-title">1. 保存位置</span>
        <button id="pickSaveDir" type="button">选择保存目录</button>
        <input id="saveDir" type="text" value="recordings" aria-label="保存目录" readonly>
        <button id="openSaveDir" type="button">打开保存目录</button>
      </div>
      <div class="row step">
        <span class="step-title">2. 采集模式</span>
        <span class="mode-group">
          <button id="modeSingle" class="mode-button active" type="button">单摄像头</button>
          <button id="modeMulti" class="mode-button" type="button">多摄像头</button>
        </span>
      </div>
      <div id="singleControls" class="row step">
        <span class="step-title">3. 摄像头</span>
        <select id="cameraSelect" aria-label="摄像头列表">
          <option value="">默认摄像头</option>
        </select>
        <button id="refreshCameras" type="button">刷新摄像头</button>
        <button id="start">打开摄像头</button>
        <span id="cameraStatus"></span>
      </div>
      <div id="multiControls" class="step hidden">
        <div class="row">
          <span class="step-title">3. 三路摄像头</span>
          <button id="refreshMultiCameras" type="button">刷新摄像头</button>
          <button id="openMultiCameras" type="button">打开全部摄像头</button>
          <span id="multiStatus"></span>
        </div>
        <div class="multi-row">
          <span class="multi-role">head</span>
          <select id="headSelect" aria-label="head 摄像头"></select>
          <span>1280 x 720</span>
          <span id="headStatus">未打开</span>
        </div>
        <div class="multi-row">
          <span class="multi-role">left</span>
          <select id="leftSelect" aria-label="left 摄像头"></select>
          <span>640 x 360</span>
          <span id="leftStatus">未打开</span>
        </div>
        <div class="multi-row">
          <span class="multi-role">right</span>
          <select id="rightSelect" aria-label="right 摄像头"></select>
          <span>640 x 360</span>
          <span id="rightStatus">未打开</span>
        </div>
      </div>
      <div class="row step">
        <span class="step-title">4. 录制</span>
        <button id="recordStart" disabled>开始录制</button>
        <button id="recordStop" disabled>停止录制</button>
        <button id="saveMode" class="toggle" type="button">自动保存：开</button>
        <button id="savePending" type="button" hidden>保存到目录</button>
      </div>
      <div class="row"><span class="label">环境</span><span id="healthStatus">正在检查...</span></div>
      <div class="row"><span class="label">浏览器</span><span id="browserStatus">正在检查...</span></div>
      <div class="row"><span class="label">保存位置</span><span id="savePath">正在读取...</span></div>
    </div>
  </header>
  <main>
    <div id="stage" class="stage">
      <video id="preview" autoplay playsinline muted></video>
    </div>
    <div id="multiStage" class="multi-stage hidden">
      <div class="multi-view multi-head">
        <canvas id="headCanvas" width="1280" height="720"></canvas>
        <span class="view-label">head 1280 x 720</span>
      </div>
      <div class="multi-view multi-left">
        <canvas id="leftCanvas" width="640" height="360"></canvas>
        <span class="view-label">left 640 x 360</span>
      </div>
      <div class="multi-view multi-right">
        <canvas id="rightCanvas" width="640" height="360"></canvas>
        <span class="view-label">right 640 x 360</span>
      </div>
    </div>
    <video id="headVideo" class="source-video" autoplay playsinline muted></video>
    <video id="leftVideo" class="source-video" autoplay playsinline muted></video>
    <video id="rightVideo" class="source-video" autoplay playsinline muted></video>
  </main>
  <footer>浏览器会请求摄像头权限；请选择允许。</footer>

  <script>
    const startButton = document.getElementById("start");
    const recordStartButton = document.getElementById("recordStart");
    const recordStopButton = document.getElementById("recordStop");
    const saveModeButton = document.getElementById("saveMode");
    const pickSaveDirButton = document.getElementById("pickSaveDir");
    const saveDirInput = document.getElementById("saveDir");
    const savePendingButton = document.getElementById("savePending");
    const openSaveDirButton = document.getElementById("openSaveDir");
    const shutdownButton = document.getElementById("shutdown");
    const cameraSelect = document.getElementById("cameraSelect");
    const refreshCamerasButton = document.getElementById("refreshCameras");
    const cameraStatusEl = document.getElementById("cameraStatus");
    const statusEl = document.getElementById("status");
    const healthStatusEl = document.getElementById("healthStatus");
    const browserStatusEl = document.getElementById("browserStatus");
    const savePathEl = document.getElementById("savePath");
    const resolutionEl = document.getElementById("resolution");
    const recordingTimeEl = document.getElementById("recordingTime");
    const downloadLink = document.getElementById("download");
    const stage = document.getElementById("stage");
    const preview = document.getElementById("preview");
    const modeSingleButton = document.getElementById("modeSingle");
    const modeMultiButton = document.getElementById("modeMulti");
    const singleControls = document.getElementById("singleControls");
    const multiControls = document.getElementById("multiControls");
    const multiStage = document.getElementById("multiStage");
    const refreshMultiCamerasButton = document.getElementById("refreshMultiCameras");
    const openMultiCamerasButton = document.getElementById("openMultiCameras");
    const multiStatusEl = document.getElementById("multiStatus");
    const multiRoles = ["head", "left", "right"];
    const multiConfig = {
      head: { width: 1280, height: 720 },
      left: { width: 640, height: 360 },
      right: { width: 640, height: 360 }
    };
    const multi = {};
    multiRoles.forEach(role => {
      multi[role] = {
        select: document.getElementById(role + "Select"),
        status: document.getElementById(role + "Status"),
        video: document.getElementById(role + "Video"),
        canvas: document.getElementById(role + "Canvas"),
        stream: null,
        drawFrame: 0,
        recorder: null,
        chunks: [],
        label: "",
        startedAt: ""
      };
    });
    let currentStream = null;
    let mediaRecorder = null;
    let recordedChunks = [];
    let activeMode = "single";
    let recordingStartedAt = 0;
    let recordingTimer = null;
    let autoSave = true;
    let pendingRecording = null;
    let multiStopState = null;
    let multiUploadSession = null;
    let multiFrameTimer = null;
    let multiFrameCount = 0;
    const multiOutputFps = 30;
    let busy = false;

    function setStatus(message, kind = "") {
      statusEl.textContent = message;
      statusEl.className = kind;
    }

    function setBusy(nextBusy) {
      busy = nextBusy;
      pickSaveDirButton.disabled = busy;
      openSaveDirButton.disabled = busy;
      shutdownButton.disabled = busy;
      saveModeButton.disabled = busy;
      cameraSelect.disabled = busy;
      refreshCamerasButton.disabled = busy;
      startButton.disabled = busy;
      modeSingleButton.disabled = busy;
      modeMultiButton.disabled = busy;
      refreshMultiCamerasButton.disabled = busy;
      openMultiCamerasButton.disabled = busy;
      multiRoles.forEach(role => {
        multi[role].select.disabled = busy;
      });
    }

    function pickMimeType() {
      if (!window.MediaRecorder) {
        return "";
      }
      const candidates = [
        "video/webm;codecs=vp9",
        "video/webm;codecs=vp8",
        "video/webm"
      ];
      return candidates.find(type => MediaRecorder.isTypeSupported(type)) || "";
    }

    function updatePreviewSize() {
      const width = preview.videoWidth;
      const height = preview.videoHeight;
      if (!width || !height) {
        return;
      }

      const maxByViewportWidth = window.innerWidth - 36;
      const maxByViewportHeight = (window.innerHeight - 150) * (width / height);
      const displayWidth = Math.max(240, Math.min(width, maxByViewportWidth, maxByViewportHeight));
      stage.style.aspectRatio = width + " / " + height;
      stage.style.width = displayWidth + "px";
      resolutionEl.textContent = width + " x " + height;
    }

    function formatDuration(ms) {
      const totalSeconds = Math.floor(ms / 1000);
      const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
      const seconds = String(totalSeconds % 60).padStart(2, "0");
      return minutes + ":" + seconds;
    }

    function startRecordingTimer() {
      recordingStartedAt = Date.now();
      recordingTimeEl.textContent = "录制中 00:00";
      recordingTimer = window.setInterval(() => {
        recordingTimeEl.textContent = "录制中 " + formatDuration(Date.now() - recordingStartedAt);
      }, 250);
    }

    function stopRecordingTimer() {
      if (recordingTimer) {
        window.clearInterval(recordingTimer);
        recordingTimer = null;
      }
    }

    function updateSaveMode() {
      saveModeButton.textContent = autoSave ? "自动保存：开" : "自动保存：关";
      saveModeButton.classList.toggle("manual", !autoSave);
      saveModeButton.setAttribute("aria-pressed", autoSave ? "true" : "false");
      saveModeButton.title = autoSave ? "Auto-save after stopping" : "Click save after stopping";
    }

    function triggerDownload() {
      if (!downloadLink.href) {
        return;
      }
      downloadLink.click();
    }

    function stopCurrentStream() {
      if (!currentStream) {
        return;
      }
      currentStream.getTracks().forEach(track => track.stop());
      currentStream = null;
      preview.srcObject = null;
    }

    function stopMultiStream(role) {
      const item = multi[role];
      if (item.drawFrame) {
        window.cancelAnimationFrame(item.drawFrame);
        item.drawFrame = 0;
      }
      if (item.stream) {
        item.stream.getTracks().forEach(track => track.stop());
        item.stream = null;
      }
      item.video.srcObject = null;
      item.label = "";
      item.status.textContent = "未打开";
      item.status.className = "";
      clearCanvas(item.canvas);
    }

    function stopAllMultiStreams() {
      multiRoles.forEach(stopMultiStream);
    }

    function clearCanvas(canvas) {
      const context = canvas.getContext("2d");
      context.fillStyle = "#050607";
      context.fillRect(0, 0, canvas.width, canvas.height);
    }

    function drawVideoToCanvas(role) {
      const item = multi[role];
      const context = item.canvas.getContext("2d");
      const target = multiConfig[role];
      context.drawImage(item.video, 0, 0, target.width, target.height);
      item.drawFrame = window.requestAnimationFrame(() => drawVideoToCanvas(role));
    }

    function setMode(mode) {
      if (busy || isRecording()) {
        setStatus("录制或保存中，不能切换模式", "warn");
        return;
      }
      activeMode = mode;
      const isSingle = mode === "single";
      modeSingleButton.classList.toggle("active", isSingle);
      modeMultiButton.classList.toggle("active", !isSingle);
      singleControls.classList.toggle("hidden", !isSingle);
      stage.classList.toggle("hidden", !isSingle);
      multiControls.classList.toggle("hidden", isSingle);
      multiStage.classList.toggle("hidden", isSingle);
      recordStartButton.disabled = true;
      recordStopButton.disabled = true;
      pendingRecording = null;
      savePendingButton.hidden = true;
      recordingTimeEl.textContent = "";
      if (isSingle) {
        stopAllMultiStreams();
        resolutionEl.textContent = "";
        setStatus(currentStream ? "单摄像头模式，摄像头已打开" : "单摄像头模式", currentStream ? "ok" : "");
        recordStartButton.disabled = !(currentStream && window.MediaRecorder);
      } else {
        stopCurrentStream();
        resolutionEl.textContent = "head 1280 x 720，left/right 640 x 360";
        setStatus("多摄像头模式，请打开 head、left、right 三路", "warn");
        updateMultiRecordButton();
      }
    }

    function isRecording() {
      if (mediaRecorder && mediaRecorder.state !== "inactive") {
        return true;
      }
      return multiRoles.some(role => multi[role].recorder && multi[role].recorder.state !== "inactive");
    }

    async function refreshCameras() {
      if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
        cameraStatusEl.textContent = "当前浏览器不支持摄像头列表";
        cameraStatusEl.className = "bad";
        multiStatusEl.textContent = "当前浏览器不支持摄像头列表";
        multiStatusEl.className = "bad";
        return;
      }

      try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const cameras = devices.filter(device => device.kind === "videoinput");
        const selected = cameraSelect.value;
        const selectedMulti = {};
        multiRoles.forEach(role => {
          selectedMulti[role] = multi[role].select.value;
        });
        cameraSelect.innerHTML = "";
        multiRoles.forEach(role => {
          multi[role].select.innerHTML = "";
        });

        if (!cameras.length) {
          const option = document.createElement("option");
          option.value = "";
          option.textContent = "未检测到摄像头";
          cameraSelect.appendChild(option);
          multiRoles.forEach(role => {
            const multiOption = option.cloneNode(true);
            multi[role].select.appendChild(multiOption);
          });
          cameraStatusEl.textContent = "未检测到摄像头";
          cameraStatusEl.className = "bad";
          multiStatusEl.textContent = "未检测到摄像头";
          multiStatusEl.className = "bad";
          startButton.disabled = true;
          openMultiCamerasButton.disabled = true;
          return;
        }

        cameras.forEach((camera, index) => {
          const option = document.createElement("option");
          option.value = camera.deviceId;
          option.textContent = camera.label || ("摄像头 " + (index + 1));
          cameraSelect.appendChild(option);
          multiRoles.forEach(role => {
            const multiOption = option.cloneNode(true);
            multi[role].select.appendChild(multiOption);
          });
        });

        if ([...cameraSelect.options].some(option => option.value === selected)) {
          cameraSelect.value = selected;
        }
        multiRoles.forEach((role, index) => {
          if ([...multi[role].select.options].some(option => option.value === selectedMulti[role])) {
            multi[role].select.value = selectedMulti[role];
          } else if (multi[role].select.options[index]) {
            multi[role].select.selectedIndex = index;
          }
        });
        cameraStatusEl.textContent = "检测到 " + cameras.length + " 个摄像头";
        cameraStatusEl.className = "ok";
        multiStatusEl.textContent = "检测到 " + cameras.length + " 个摄像头";
        multiStatusEl.className = "ok";
        startButton.disabled = false;
        openMultiCamerasButton.disabled = false;
      } catch (err) {
        console.error(err);
        cameraStatusEl.textContent = "读取摄像头列表失败";
        cameraStatusEl.className = "bad";
        multiStatusEl.textContent = "读取摄像头列表失败";
        multiStatusEl.className = "bad";
      }
    }

    function cameraConstraints() {
      const video = {
        width: { ideal: 1920 },
        height: { ideal: 1080 },
        frameRate: { ideal: multiOutputFps, max: multiOutputFps }
      };
      if (cameraSelect.value) {
        video.deviceId = { exact: cameraSelect.value };
      }
      return { video, audio: false };
    }

    function multiCameraConstraints(role) {
      const target = multiConfig[role];
      const video = {
        width: { ideal: target.width },
        height: { ideal: target.height },
        aspectRatio: { ideal: 16 / 9 },
        frameRate: { ideal: 30 }
      };
      const deviceId = multi[role].select.value;
      if (deviceId) {
        video.deviceId = { exact: deviceId };
      }
      return { video, audio: false };
    }

    function multiReady() {
      return multiRoles.every(role => Boolean(multi[role].stream));
    }

    function updateMultiRecordButton() {
      recordStartButton.disabled = !(activeMode === "multi" && multiReady() && window.MediaRecorder && !busy);
    }

    async function startCamera() {
      startButton.disabled = true;
      setStatus("正在打开摄像头...");
      try {
        stopCurrentStream();
        const stream = await navigator.mediaDevices.getUserMedia(cameraConstraints());
        currentStream = stream;
        preview.srcObject = stream;
        await preview.play();
        updatePreviewSize();
        await refreshCameras();
        recordStartButton.disabled = !window.MediaRecorder;
        const track = currentStream.getVideoTracks()[0];
        cameraStatusEl.textContent = track && track.label ? "Current: " + track.label : "Current camera opened";
        cameraStatusEl.className = "ok";
        setStatus(window.MediaRecorder ? "Camera opened" : "Camera opened, but this browser cannot record", window.MediaRecorder ? "ok" : "warn");
      } catch (err) {
        setStatus(cameraErrorMessage(err), "bad");
        startButton.disabled = false;
      }
    }

    async function openMultiCameraRole(role) {
      const item = multi[role];
      const target = multiConfig[role];
      stopMultiStream(role);
      item.status.textContent = "正在打开...";
      item.status.className = "warn";
      const stream = await navigator.mediaDevices.getUserMedia(multiCameraConstraints(role));
      item.stream = stream;
      item.video.srcObject = stream;
      await item.video.play();
      item.canvas.width = target.width;
      item.canvas.height = target.height;
      drawVideoToCanvas(role);
      const track = stream.getVideoTracks()[0];
      const settings = track ? track.getSettings() : {};
      item.label = track && track.label ? track.label : role;
      item.status.textContent = item.label + "，输入 " + (settings.width || "?") + " x " + (settings.height || "?") + "，输出 " + target.width + " x " + target.height;
      item.status.className = "ok";
    }

    async function switchMultiCameraRole(role) {
      if (busy || isRecording()) {
        setStatus("录制或保存中，不能切换摄像头", "warn");
        return;
      }
      setBusy(true);
      recordStartButton.disabled = true;
      setStatus("正在切换 " + role + " 摄像头...");
      multiStatusEl.textContent = "正在切换 " + role + "...";
      multiStatusEl.className = "warn";

      try {
        await openMultiCameraRole(role);
        multiStatusEl.textContent = role + " 摄像头已切换";
        multiStatusEl.className = "ok";
        setStatus(role + " 摄像头已切换", "ok");
      } catch (err) {
        console.error(err);
        stopMultiStream(role);
        multiStatusEl.textContent = role + " " + cameraErrorMessage(err);
        multiStatusEl.className = "bad";
        setStatus(role + " " + cameraErrorMessage(err), "bad");
      } finally {
        setBusy(false);
        updateMultiRecordButton();
      }
    }

    async function openMultiCameras() {
      setBusy(true);
      setStatus("正在打开三路摄像头...");
      multiStatusEl.textContent = "正在打开...";
      multiStatusEl.className = "warn";

      try {
        stopAllMultiStreams();
        for (const role of multiRoles) {
          await openMultiCameraRole(role);
        }
        await refreshCameras();
        multiStatusEl.textContent = "三路摄像头已打开";
        multiStatusEl.className = "ok";
        setStatus("三路摄像头已打开，可以开始录制", "ok");
      } catch (err) {
        console.error(err);
        stopAllMultiStreams();
        multiStatusEl.textContent = cameraErrorMessage(err);
        multiStatusEl.className = "bad";
        setStatus(cameraErrorMessage(err), "bad");
      } finally {
        setBusy(false);
        updateMultiRecordButton();
      }
    }

    function startRecording() {
      if (activeMode === "multi") {
        startMultiRecording();
        return;
      }
      if (!currentStream || !window.MediaRecorder) {
        return;
      }

      recordedChunks = [];
      pendingRecording = null;
      savePendingButton.hidden = true;
      downloadLink.hidden = true;
      if (downloadLink.href) {
        URL.revokeObjectURL(downloadLink.href);
        downloadLink.removeAttribute("href");
      }

      const mimeType = pickMimeType();
      const options = mimeType ? { mimeType } : {};
      mediaRecorder = new MediaRecorder(currentStream, options);
      mediaRecorder.addEventListener("dataavailable", event => {
        if (event.data && event.data.size > 0) {
          recordedChunks.push(event.data);
        }
      });
      mediaRecorder.addEventListener("stop", () => {
        stopRecordingTimer();
        const recordedDuration = Date.now() - recordingStartedAt;
        const sourceType = mediaRecorder.mimeType || "video/webm";
        const sourceBlob = new Blob(recordedChunks, { type: sourceType });
        const stamp = new Date().toISOString().replace(/[:.]/g, "-");
        const filename = "camera-recording-" + stamp;

        recordingTimeEl.textContent = "录制完成 " + formatDuration(recordedDuration);
        pendingRecording = { mode: "single", blob: sourceBlob, filename };
        if (autoSave) {
          savePendingRecording();
        } else {
          savePendingButton.hidden = false;
          setBusy(false);
          setStatus("录制已停止，等待手动保存", "warn");
          recordStartButton.disabled = false;
          recordStopButton.disabled = true;
        }
      });

      mediaRecorder.start(1000);
      startRecordingTimer();
      setBusy(true);
      recordStartButton.disabled = true;
      recordStopButton.disabled = false;
      setStatus("正在录制", "ok");
    }

    function canvasStreamForRole(role) {
      const item = multi[role];
      if (!item.canvas.captureStream) {
        throw new Error("Current browser does not support canvas recording");
      }
      return item.canvas.captureStream(0);
    }

    function drawAlignedMultiFrame() {
      multiRoles.forEach(role => {
        const item = multi[role];
        const context = item.canvas.getContext("2d");
        const target = multiConfig[role];
        context.drawImage(item.video, 0, 0, target.width, target.height);
        if (item.recordTrack && item.recordTrack.requestFrame) {
          item.recordTrack.requestFrame();
        }
      });
      multiFrameCount += 1;
    }

    function startAlignedMultiClock() {
      stopAlignedMultiClock();
      multiFrameCount = 0;
      const frameInterval = 1000 / multiOutputFps;
      let nextFrameAt = performance.now();

      const tick = () => {
        const now = performance.now();
        while (nextFrameAt <= now + 1) {
          drawAlignedMultiFrame();
          nextFrameAt += frameInterval;
        }
        multiFrameTimer = window.setTimeout(tick, Math.max(0, nextFrameAt - performance.now()));
      };
      tick();
    }

    function stopAlignedMultiClock() {
      if (multiFrameTimer) {
        window.clearTimeout(multiFrameTimer);
        multiFrameTimer = null;
      }
    }

    async function startMultiRecording() {
      if (!multiReady() || !window.MediaRecorder) {
        setStatus("Open head, left, and right cameras first", "warn");
        return;
      }

      pendingRecording = null;
      savePendingButton.hidden = true;
      downloadLink.hidden = true;
      if (downloadLink.href) {
        URL.revokeObjectURL(downloadLink.href);
        downloadLink.removeAttribute("href");
      }

      const startedAt = new Date().toISOString();
      const streams = {};
      multiRoles.forEach(role => {
        const item = multi[role];
        const target = multiConfig[role];
        streams[role] = {
          camera_label: item.label,
          width: target.width,
          height: target.height
        };
      });

      multiStopState = {
        count: 0,
        startedAt,
        stoppedAt: "",
        durationMs: 0,
        failed: false,
        metadata: {
          mode: "multi",
          started_at: startedAt,
          stopped_at: "",
          duration_ms: 0,
          fps: multiOutputFps,
          frame_count: 0,
          frame_interval_ms: 1000 / multiOutputFps,
          streams
        }
      };

      setBusy(true);
      recordStartButton.disabled = true;
      recordStopButton.disabled = true;
      setStatus("Creating multi-camera recording session...", "warn");

      try {
        multiUploadSession = await startMultiRecordingSession(multiStopState.metadata);
      } catch (err) {
        console.error(err);
        multiStopState = null;
        multiUploadSession = null;
        setBusy(false);
        updateMultiRecordButton();
        setStatus("Failed to create recording session", "bad");
        return;
      }

      const mimeType = pickMimeType();
      const options = mimeType ? { mimeType } : {};
      try {
        multiRoles.forEach(role => {
          const item = multi[role];
          item.chunks = [];
          item.uploadChain = Promise.resolve();
          item.uploadError = null;
          const stream = canvasStreamForRole(role);
          item.recordTrack = stream.getVideoTracks()[0];
          item.recorder = new MediaRecorder(stream, options);
          item.startedAt = startedAt;
          item.recorder.addEventListener("dataavailable", event => {
            if (event.data && event.data.size > 0) {
              item.uploadChain = item.uploadChain
                .then(() => appendMultiRecordingChunk(multiUploadSession.session_id, role, event.data))
                .catch(err => {
                  item.uploadError = err;
                  if (multiStopState) {
                    multiStopState.failed = true;
                  }
                  console.error(err);
                  const detail = err && err.message ? (" - " + err.message) : "";
                  setStatus("Recording chunk upload failed" + detail, "bad");
                });
            }
          });
          item.recorder.addEventListener("stop", async () => {
            await item.uploadChain;
            if (!multiStopState) {
              return;
            }
            multiStopState.count += 1;
            if (multiStopState.count === multiRoles.length) {
              finishMultiRecording();
            }
          });
        });
        multiRoles.forEach(role => multi[role].recorder.start(1000));
        startAlignedMultiClock();
      } catch (err) {
        console.error(err);
        stopAlignedMultiClock();
        if (multiUploadSession) {
          abortMultiRecordingSession(multiUploadSession.session_id);
        }
        multiUploadSession = null;
        multiStopState = null;
        setBusy(false);
        updateMultiRecordButton();
        setStatus(err.message || "Failed to start multi-camera recording", "bad");
        return;
      }

      startRecordingTimer();
      recordStartButton.disabled = true;
      recordStopButton.disabled = false;
      setStatus("Recording three cameras", "ok");
    }

    function finishMultiRecording() {
      stopAlignedMultiClock();
      stopRecordingTimer();
      if (!multiStopState) {
        return;
      }
      const stoppedAt = new Date().toISOString();
      const recordedDuration = Date.now() - recordingStartedAt;
      multiStopState.stoppedAt = stoppedAt;
      multiStopState.durationMs = recordedDuration;
      multiStopState.metadata.stopped_at = stoppedAt;
      multiStopState.metadata.duration_ms = recordedDuration;
      multiStopState.metadata.frame_count = multiFrameCount;
      recordingTimeEl.textContent = "Recorded " + formatDuration(recordedDuration);

      pendingRecording = {
        mode: "multi_session",
        sessionId: multiUploadSession ? multiUploadSession.session_id : "",
        metadata: multiStopState.metadata
      };
      const uploadFailed = multiStopState.failed || multiRoles.some(role => multi[role].uploadError);
      multiStopState = null;
      multiUploadSession = null;

      if (uploadFailed || !pendingRecording.sessionId) {
        savePendingButton.hidden = false;
        setBusy(false);
        setStatus("Recording stopped, but chunk upload failed. Retry saving.", "bad");
        updateMultiRecordButton();
        recordStopButton.disabled = true;
        return;
      }

      if (autoSave) {
        savePendingRecording();
      } else {
        savePendingButton.hidden = false;
        setBusy(false);
        setStatus("Recording stopped. Waiting for manual save.", "warn");
        updateMultiRecordButton();
        recordStopButton.disabled = true;
      }
    }

    async function saveRecordingToServer(blob, filename) {
      const response = await fetch(
        "/save-recording?name=" + encodeURIComponent(filename) +
        "&dir=" + encodeURIComponent(saveDirInput.value.trim()),
        {
        method: "POST",
        headers: {
          "Content-Type": blob.type || "application/octet-stream"
        },
        body: blob
        }
      );
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || "Save failed");
      }
      return await response.json();
    }

    async function startMultiRecordingSession(metadata) {
      const response = await fetch("/multi-recording/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dir: saveDirInput.value.trim(),
          metadata
        })
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || "Start session failed");
      }
      return await response.json();
    }

    async function appendMultiRecordingChunk(sessionId, role, blob) {
      const response = await fetch(
        "/multi-recording/append?session=" + encodeURIComponent(sessionId) +
        "&role=" + encodeURIComponent(role),
        {
          method: "POST",
          headers: { "Content-Type": blob.type || "application/octet-stream" },
          body: blob
        }
      );
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || "Append chunk failed");
      }
    }

    async function finishMultiRecordingSession(recording) {
      const response = await fetch("/multi-recording/finish", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: recording.sessionId,
          metadata: recording.metadata
        })
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || "Finish session failed");
      }
      return await response.json();
    }

    async function abortMultiRecordingSession(sessionId) {
      try {
        await fetch("/multi-recording/abort", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId })
        });
      } catch (err) {
        console.error(err);
      }
    }

    async function savePendingRecording() {
      if (!pendingRecording) {
        return;
      }

      savePendingButton.disabled = true;
      recordStartButton.disabled = true;
      recordStopButton.disabled = true;
      setStatus("正在转换并保存 MP4，请勿关闭页面...", "warn");

      try {
        let result;
        if (pendingRecording.mode === "multi_session") {
          result = await finishMultiRecordingSession(pendingRecording);
          savePathEl.textContent = result.files.head;
          setStatus("已保存三路：" + result.index.toString().padStart(6, "0"), "ok");
        } else {
          const { blob, filename } = pendingRecording;
          result = await saveRecordingToServer(blob, filename);
          savePathEl.textContent = result.path;
          setStatus("已保存：" + result.path, "ok");
        }
        pendingRecording = null;
        savePendingButton.hidden = true;
      } catch (err) {
        console.error(err);
        if (pendingRecording.mode === "single") {
          setDownload(pendingRecording.blob, pendingRecording.filename + ".webm", "下载 WebM 备份");
        } else {
          savePendingButton.hidden = false;
        }
        setStatus("保存失败，请重试或检查 ffmpeg", "bad");
      } finally {
        setBusy(false);
        savePendingButton.disabled = false;
        recordStartButton.disabled = activeMode === "multi" ? !multiReady() : !currentStream;
        recordStopButton.disabled = true;
      }
    }

    function setDownload(blob, filename, label) {
      if (downloadLink.href) {
        URL.revokeObjectURL(downloadLink.href);
      }
      const url = URL.createObjectURL(blob);
      downloadLink.href = url;
      downloadLink.download = filename;
      downloadLink.hidden = false;
      downloadLink.textContent = label;
    }

    function stopRecording() {
      if (activeMode === "multi") {
        stopAlignedMultiClock();
        multiRoles.forEach(role => {
          const recorder = multi[role].recorder;
          if (recorder && recorder.state !== "inactive") {
            recorder.stop();
          }
        });
        recordStopButton.disabled = true;
        setStatus("正在停止三路录制...", "warn");
        return;
      }
      if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
      }
    }

    async function pickSaveDir() {
      pickSaveDirButton.disabled = true;
      setStatus("等待选择保存目录...");
      try {
        const response = await fetch("/pick-save-dir", { method: "POST" });
        if (!response.ok) {
          const detail = await response.text();
          throw new Error(detail || "Pick directory failed");
        }
        const result = await response.json();
        if (result.cancelled) {
          setStatus("已取消选择目录", "warn");
          return;
        }
        saveDirInput.value = result.path;
        savePathEl.textContent = result.path;
        setStatus("保存目录：" + result.path, "ok");
      } catch (err) {
        console.error(err);
        setStatus("选择目录失败", "bad");
      } finally {
        pickSaveDirButton.disabled = false;
      }
    }

    async function loadSaveDir() {
      try {
        const response = await fetch("/save-dir");
        if (!response.ok) {
          return;
        }
        const result = await response.json();
        saveDirInput.value = result.path;
        savePathEl.textContent = result.path;
      } catch (err) {
        console.error(err);
      }
    }

    function cameraErrorMessage(err) {
      const messages = {
        NotAllowedError: "摄像头权限被拒绝，请在浏览器地址栏允许摄像头权限",
        NotFoundError: "未检测到摄像头，请检查 USB 连接",
        NotReadableError: "Camera may be in use by another program",
        OverconstrainedError: "当前分辨率或帧率不支持，请换摄像头或降低要求",
        SecurityError: "浏览器安全策略阻止摄像头访问，请使用 localhost 页面"
      };
      return messages[err.name] || ("Open failed: " + err.name + " - " + err.message);
    }

    function checkBrowserCapabilities() {
      const problems = [];
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        problems.push("不支持摄像头 API");
      }
      if (!window.MediaRecorder) {
        problems.push("不支持录制 API");
      } else if (!pickMimeType()) {
        problems.push("不支持 WebM 录制");
      }

      if (problems.length) {
        browserStatusEl.textContent = problems.join("; ") + ". Please use the latest Chrome, Edge, or Firefox.";
        browserStatusEl.className = "bad";
        return;
      }

      browserStatusEl.textContent = "可用";
      browserStatusEl.className = "ok";
    }

    async function loadHealth() {
      try {
        const response = await fetch("/health");
        if (!response.ok) {
          throw new Error("health failed");
        }
        const health = await response.json();
        const parts = [
          "系统：" + health.platform,
          "ffmpeg: " + (health.ffmpeg ? "available" : "missing"),
          "目录选择：" + (health.directory_picker ? "可用" : "不可用")
        ];
        if (health.video_devices !== null) {
          parts.push("摄像头设备：" + health.video_devices);
        }
        healthStatusEl.textContent = parts.join("; ");
        healthStatusEl.className = health.ffmpeg ? "ok" : "bad";
      } catch (err) {
        console.error(err);
        healthStatusEl.textContent = "环境检查失败";
        healthStatusEl.className = "bad";
      }
    }

    async function openSaveDir() {
      try {
        const response = await fetch("/open-save-dir", { method: "POST" });
        if (!response.ok) {
          const detail = await response.text();
          throw new Error(detail || "open failed");
        }
        setStatus("已请求打开保存目录", "ok");
      } catch (err) {
        console.error(err);
        setStatus("打开保存目录失败", "bad");
      }
    }

    async function shutdownApp() {
      if (busy || isRecording()) {
        setStatus("录制或保存中，不能退出", "warn");
        return;
      }
      try {
        await fetch("/shutdown", { method: "POST" });
        document.body.innerHTML = "<main><p>程序正在退出，可以关闭这个页面。</p></main>";
      } catch (err) {
        console.error(err);
      }
    }

    modeSingleButton.addEventListener("click", () => setMode("single"));
    modeMultiButton.addEventListener("click", () => setMode("multi"));
    startButton.addEventListener("click", startCamera);
    openMultiCamerasButton.addEventListener("click", openMultiCameras);
    recordStartButton.addEventListener("click", startRecording);
    recordStopButton.addEventListener("click", stopRecording);
    savePendingButton.addEventListener("click", savePendingRecording);
    saveModeButton.addEventListener("click", () => {
      autoSave = !autoSave;
      updateSaveMode();
    });
    pickSaveDirButton.addEventListener("click", pickSaveDir);
    openSaveDirButton.addEventListener("click", openSaveDir);
    shutdownButton.addEventListener("click", shutdownApp);
    refreshCamerasButton.addEventListener("click", refreshCameras);
    refreshMultiCamerasButton.addEventListener("click", refreshCameras);
    cameraSelect.addEventListener("change", () => {
      if (currentStream && !busy) {
        startCamera();
      } else {
        setStatus("已选择摄像头，点击打开摄像头生效");
      }
    });
    multiRoles.forEach(role => {
      multi[role].select.addEventListener("change", () => {
        if (multi[role].stream) {
          switchMultiCameraRole(role);
        } else {
          updateMultiRecordButton();
          setStatus("已选择 " + role + " 摄像头，点击打开全部摄像头生效");
        }
      });
    });
    preview.addEventListener("loadedmetadata", updatePreviewSize);
    window.addEventListener("resize", updatePreviewSize);
    window.addEventListener("beforeunload", event => {
      if (busy || isRecording()) {
        event.preventDefault();
        event.returnValue = "";
      }
    });
    multiRoles.forEach(role => clearCanvas(multi[role].canvas));
    updateSaveMode();
    checkBrowserCapabilities();
    loadHealth();
    loadSaveDir();
    refreshCameras();
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setStatus("当前浏览器不支持摄像头 API", "bad");
      startButton.disabled = true;
    }
  </script>
</body>
</html>
"""


def server_camera_html() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Camera Stream</title>
  <style>
    :root {
      color-scheme: dark;
      font-family: Arial, Helvetica, sans-serif;
      background: #101316;
      color: #f1f5f9;
    }
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; padding: 18px; }
    img {
      width: min(100%, 1280px);
      max-height: calc(100vh - 36px);
      background: #050607;
      border: 1px solid #303943;
      border-radius: 8px;
      object-fit: contain;
    }
  </style>
</head>
<body>
  <img src="/stream.mjpg" alt="摄像头画面">
</body>
</html>
"""


def resolve_save_dir(path: str) -> str:
    expanded = os.path.expanduser(path.strip() or "recordings")
    if not os.path.isabs(expanded):
        expanded = os.path.join(os.getcwd(), expanded)
    return os.path.abspath(expanded)


def next_numbered_recording_path(save_dir: str) -> str:
    max_index = -1
    try:
        names = os.listdir(save_dir)
    except OSError:
        names = []

    for name in names:
        root, ext = os.path.splitext(name)
        if ext.lower() == ".mp4" and len(root) == 6 and root.isdigit():
            max_index = max(max_index, int(root))

    next_index = max_index + 1
    while True:
        candidate = os.path.join(save_dir, f"{next_index:06d}.mp4")
        if not os.path.exists(candidate):
            return candidate
        next_index += 1


def next_multi_recording_index(save_dir: str) -> int:
    max_index = -1
    for role in ("head", "left", "right"):
        role_dir = os.path.join(save_dir, role)
        try:
            names = os.listdir(role_dir)
        except OSError:
            names = []
        for name in names:
            root, ext = os.path.splitext(name)
            if ext.lower() == ".mp4" and len(root) == 6 and root.isdigit():
                max_index = max(max_index, int(root))

    next_index = max_index + 1
    while True:
        stem = f"{next_index:06d}"
        paths = [os.path.join(save_dir, role, f"{stem}.mp4") for role in ("head", "left", "right")]
        paths.append(os.path.join(save_dir, "metadata", f"{stem}.json"))
        if not any(os.path.exists(path) for path in paths):
            return next_index
        next_index += 1


def app_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def bundled_resource_dir() -> str:
    return getattr(sys, "_MEIPASS", app_base_dir())


def find_ffmpeg() -> str | None:
    env_path = os.environ.get("FFMPEG_PATH")
    if env_path and os.path.exists(env_path):
        return env_path

    executable = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
    candidates = [
        os.path.join(app_base_dir(), "third_party", "ffmpeg", "windows", executable),
        os.path.join(app_base_dir(), "ffmpeg", executable),
        os.path.join(app_base_dir(), executable),
        os.path.join(bundled_resource_dir(), "third_party", "ffmpeg", "windows", executable),
        os.path.join(bundled_resource_dir(), "ffmpeg", executable),
        os.path.join(bundled_resource_dir(), executable),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate

    return shutil.which("ffmpeg")


def convert_webm_to_mp4(data: bytes, output_size: tuple[int, int] | None = None) -> bytes:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found")

    with tempfile.TemporaryDirectory(prefix="webcam-recording-") as tmpdir:
        input_path = os.path.join(tmpdir, "recording.webm")
        output_path = os.path.join(tmpdir, "recording.mp4")

        with open(input_path, "wb") as f:
            f.write(data)

        cmd = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            input_path,
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
        ]
        if output_size:
            width, height = output_size
            cmd.extend(["-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"])
        cmd.append(output_path)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode:
            message = result.stderr.strip() or "ffmpeg failed"
            raise RuntimeError(message)

        with open(output_path, "rb") as f:
            return f.read()


def convert_webm_file_to_mp4_file(
    input_path: str,
    output_path: str,
    output_size: tuple[int, int],
    fps: int,
    frame_count: int,
) -> None:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found")

    width, height = output_size
    filters = [
        f"fps={fps}",
        f"scale={width}:{height}:force_original_aspect_ratio=decrease",
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
        "tpad=stop_mode=clone:stop_duration=3600",
        f"trim=end_frame={frame_count}",
        f"setpts=N/{fps}/TB",
    ]
    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        input_path,
        "-an",
        "-vf",
        ",".join(filters),
        "-frames:v",
        str(frame_count),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode:
        message = result.stderr.strip() or "ffmpeg failed"
        raise RuntimeError(message)


def pick_directory_with_native_dialog(initial_dir: str) -> str | None:
    if shutil.which("zenity"):
        cmd = [
            "zenity",
            "--file-selection",
            "--directory",
            "--title=选择保存目录",
            f"--filename={initial_dir.rstrip(os.sep)}{os.sep}",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip() or None
        if result.returncode == 1:
            return None
        raise RuntimeError(result.stderr.strip() or "zenity failed")

    if shutil.which("kdialog"):
        result = subprocess.run(
            ["kdialog", "--getexistingdirectory", initial_dir],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
        if result.returncode == 1:
            return None
        raise RuntimeError(result.stderr.strip() or "kdialog failed")

    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        raise RuntimeError("No native directory picker found") from exc

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory(initialdir=initial_dir, title="选择保存目录")
        return selected or None
    finally:
        root.destroy()


def has_directory_picker() -> bool:
    return bool(shutil.which("zenity") or shutil.which("kdialog")) or tkinter_available()


def tkinter_available() -> bool:
    try:
        import tkinter  # noqa: F401
    except ImportError:
        return False
    return True


def count_video_devices() -> int | None:
    if platform.system() != "Linux":
        return None
    try:
        return len([name for name in os.listdir("/dev") if name.startswith("video")])
    except OSError:
        return 0


def open_path(path: str) -> None:
    system = platform.system()
    if system == "Windows":
        os.startfile(path)  # type: ignore[attr-defined]
        return
    if system == "Darwin":
        subprocess.Popen(["open", path])
        return
    opener = shutil.which("xdg-open")
    if not opener:
        raise RuntimeError("xdg-open not found")
    subprocess.Popen([opener, path])


def parse_multipart_form(headers, data: bytes) -> tuple[dict[str, str], dict[str, bytes]]:
    content_type = headers.get("Content-Type", "")
    if not content_type.lower().startswith("multipart/form-data"):
        raise ValueError("Expected multipart/form-data")

    raw_message = (
        f"Content-Type: {content_type}\r\n"
        "MIME-Version: 1.0\r\n"
        "\r\n"
    ).encode("utf-8") + data
    message = BytesParser(policy=email_policy).parsebytes(raw_message)
    if not message.is_multipart():
        raise ValueError("Invalid multipart body")

    fields: dict[str, str] = {}
    files: dict[str, bytes] = {}
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        payload = part.get_payload(decode=True) or b""
        filename = part.get_filename()
        if filename:
            files[name] = payload
        else:
            charset = part.get_content_charset() or "utf-8"
            fields[name] = payload.decode(charset, errors="replace")
    return fields, files


def find_available_port(host: str, preferred_port: int, attempts: int = 50) -> int:
    for port in range(preferred_port, preferred_port + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"No available port from {preferred_port} to {preferred_port + attempts - 1}")


def delayed_shutdown(server: ThreadingHTTPServer) -> None:
    time.sleep(0.2)
    server.shutdown()


class CameraServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], handler_class: type[BaseHTTPRequestHandler], args: argparse.Namespace):
        super().__init__(server_address, handler_class)
        self.args = args
        self.save_dir = resolve_save_dir(args.save_dir)
        self.save_lock = threading.Lock()
        self.sessions: dict[str, dict[str, object]] = {}
        self.sessions_lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    server: CameraServer

    def log_message(self, fmt: str, *args: object) -> None:
        print("%s - %s" % (self.address_string(), fmt % args))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._send_html(server_camera_html() if self.server.args.server_camera else CLIENT_CAMERA_HTML)
            return
        if parsed.path == "/health":
            self._health()
            return
        if parsed.path == "/save-dir":
            self._send_json({"path": self.server.save_dir})
            return
        if parsed.path == "/stream.mjpg" and self.server.args.server_camera:
            self._stream_server_camera()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/set-save-dir":
            self._set_save_dir()
            return
        if parsed.path == "/pick-save-dir":
            self._pick_save_dir()
            return
        if parsed.path == "/open-save-dir":
            self._open_save_dir()
            return
        if parsed.path == "/shutdown":
            self._shutdown()
            return
        if parsed.path == "/save-recording":
            query = parse_qs(parsed.query)
            self._save_recording(query)
            return
        if parsed.path == "/save-multi-recording":
            self._save_multi_recording()
            return
        if parsed.path == "/multi-recording/start":
            self._start_multi_recording_session()
            return
        if parsed.path == "/multi-recording/append":
            query = parse_qs(parsed.query)
            self._append_multi_recording_chunk(query)
            return
        if parsed.path == "/multi-recording/finish":
            self._finish_multi_recording_session()
            return
        if parsed.path == "/multi-recording/abort":
            self._abort_multi_recording_session()
            return
        if parsed.path == "/convert-to-mp4":
            self._convert_to_mp4()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def _send_html(self, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _health(self) -> None:
        self._send_json(
            {
                "platform": platform.system(),
                "python": platform.python_version(),
                "ffmpeg": bool(find_ffmpeg()),
                "ffmpeg_path": find_ffmpeg() or "",
                "directory_picker": has_directory_picker(),
                "video_devices": count_video_devices(),
                "save_dir": self.server.save_dir,
            }
        )

    def _send_json(self, body: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _read_request_body(self) -> bytes | None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid Content-Length")
            return None

        if content_length <= 0:
            self.send_error(HTTPStatus.BAD_REQUEST, "Empty request body")
            return None

        return self.rfile.read(content_length)

    def _set_save_dir(self) -> None:
        data = self._read_request_body()
        if data is None:
            return

        try:
            payload = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON")
            return

        save_dir = str(payload.get("dir", "")).strip()
        if not save_dir:
            self.send_error(HTTPStatus.BAD_REQUEST, "Save directory is required")
            return

        try:
            resolved = resolve_save_dir(save_dir)
            os.makedirs(resolved, exist_ok=True)
        except OSError as exc:
            self.send_error(HTTPStatus.BAD_REQUEST, f"Cannot create save directory: {exc}")
            return

        self.server.save_dir = resolved
        self._send_json({"path": resolved})

    def _pick_save_dir(self) -> None:
        try:
            selected = pick_directory_with_native_dialog(self.server.save_dir)
        except RuntimeError as exc:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
            return

        if selected is None:
            self._send_json({"cancelled": True, "path": self.server.save_dir})
            return

        try:
            resolved = resolve_save_dir(selected)
            os.makedirs(resolved, exist_ok=True)
        except OSError as exc:
            self.send_error(HTTPStatus.BAD_REQUEST, f"Cannot create save directory: {exc}")
            return

        self.server.save_dir = resolved
        self._send_json({"cancelled": False, "path": resolved})

    def _open_save_dir(self) -> None:
        try:
            os.makedirs(self.server.save_dir, exist_ok=True)
            open_path(self.server.save_dir)
        except (OSError, RuntimeError) as exc:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
            return
        self._send_json({"ok": True, "path": self.server.save_dir})

    def _shutdown(self) -> None:
        self._send_json({"ok": True})
        threading.Thread(target=delayed_shutdown, args=(self.server,), daemon=True).start()

    def _save_recording(self, query: dict[str, list[str]]) -> None:
        requested_dir = query.get("dir", [""])[0].strip()

        try:
            save_dir = resolve_save_dir(requested_dir) if requested_dir else self.server.save_dir
            os.makedirs(save_dir, exist_ok=True)
        except OSError as exc:
            self.send_error(HTTPStatus.BAD_REQUEST, f"Cannot create save directory: {exc}")
            return

        data = self._read_request_body()
        if data is None:
            return

        try:
            mp4_data = convert_webm_to_mp4(data)
        except RuntimeError as exc:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
            return

        with self.server.save_lock:
            output_path = next_numbered_recording_path(save_dir)
            try:
                with open(output_path, "wb") as f:
                    f.write(mp4_data)
            except OSError as exc:
                self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Cannot write recording: {exc}")
                return

        self.server.save_dir = save_dir
        self._send_json({"path": output_path, "filename": os.path.basename(output_path)})

    def _save_multi_recording(self) -> None:
        data = self._read_request_body()
        if data is None:
            return

        try:
            fields, files = parse_multipart_form(self.headers, data)
        except ValueError as exc:
            self.send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return

        missing = [role for role in ("head", "left", "right") if role not in files or not files[role]]
        if missing:
            self.send_error(HTTPStatus.BAD_REQUEST, f"Missing recording: {', '.join(missing)}")
            return

        requested_dir = fields.get("dir", "").strip()
        try:
            save_dir = resolve_save_dir(requested_dir) if requested_dir else self.server.save_dir
            for name in ("head", "left", "right", "metadata"):
                os.makedirs(os.path.join(save_dir, name), exist_ok=True)
        except OSError as exc:
            self.send_error(HTTPStatus.BAD_REQUEST, f"Cannot create save directory: {exc}")
            return

        metadata: dict[str, object]
        metadata_raw = fields.get("metadata", "{}")
        try:
            parsed_metadata = json.loads(metadata_raw)
            metadata = parsed_metadata if isinstance(parsed_metadata, dict) else {}
        except json.JSONDecodeError:
            metadata = {}

        role_sizes = {
            "head": (1280, 720),
            "left": (640, 360),
            "right": (640, 360),
        }

        with self.server.save_lock:
            index = next_multi_recording_index(save_dir)
            stem = f"{index:06d}"
            output_paths = {
                role: os.path.join(save_dir, role, f"{stem}.mp4")
                for role in ("head", "left", "right")
            }
            metadata_path = os.path.join(save_dir, "metadata", f"{stem}.json")

            try:
                converted = {
                    role: convert_webm_to_mp4(files[role], role_sizes[role])
                    for role in ("head", "left", "right")
                }
                for role, output_path in output_paths.items():
                    with open(output_path, "wb") as f:
                        f.write(converted[role])
            except (OSError, RuntimeError) as exc:
                self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Cannot save multi recording: {exc}")
                return

            metadata["mode"] = "multi"
            metadata["index"] = index
            streams = metadata.get("streams")
            if not isinstance(streams, dict):
                streams = {}
            for role in ("head", "left", "right"):
                role_stream = streams.get(role)
                if not isinstance(role_stream, dict):
                    role_stream = {}
                role_stream["file"] = f"{role}/{stem}.mp4"
                role_stream["width"] = role_sizes[role][0]
                role_stream["height"] = role_sizes[role][1]
                streams[role] = role_stream
            metadata["streams"] = streams

            try:
                with open(metadata_path, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=2)
                    f.write("\n")
            except OSError as exc:
                self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Cannot write metadata: {exc}")
                return

        self.server.save_dir = save_dir
        response_files = {role: path for role, path in output_paths.items()}
        response_files["metadata"] = metadata_path
        self._send_json({"index": index, "files": response_files})

    def _start_multi_recording_session(self) -> None:
        data = self._read_request_body()
        if data is None:
            return

        try:
            payload = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON")
            return

        requested_dir = str(payload.get("dir", "")).strip()
        try:
            save_dir = resolve_save_dir(requested_dir) if requested_dir else self.server.save_dir
            for name in ("head", "left", "right", "metadata"):
                os.makedirs(os.path.join(save_dir, name), exist_ok=True)
        except OSError as exc:
            self.send_error(HTTPStatus.BAD_REQUEST, f"Cannot create save directory: {exc}")
            return

        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        session_id = uuid.uuid4().hex
        session_root = os.path.join(save_dir, "_camera_sessions")
        session_dir = os.path.join(session_root, session_id)
        try:
            os.makedirs(session_root, exist_ok=True)
            os.makedirs(session_dir, exist_ok=False)
        except OSError as exc:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Cannot create session: {exc}")
            return

        paths = {role: os.path.join(session_dir, f"{role}.webm") for role in ("head", "left", "right")}
        with self.server.sessions_lock:
            self.server.sessions[session_id] = {
                "dir": session_dir,
                "save_dir": save_dir,
                "metadata": metadata,
                "paths": paths,
                "lock": threading.Lock(),
            }

        self.server.save_dir = save_dir
        self._send_json({"session_id": session_id})

    def _append_multi_recording_chunk(self, query: dict[str, list[str]]) -> None:
        session_id = query.get("session", [""])[0].strip()
        role = query.get("role", [""])[0].strip()
        if role not in ("head", "left", "right"):
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid role")
            return

        data = self._read_request_body()
        if data is None:
            return

        with self.server.sessions_lock:
            session = self.server.sessions.get(session_id)
        if not session:
            self.send_error(HTTPStatus.NOT_FOUND, "Recording session not found")
            return

        paths = session["paths"]
        if not isinstance(paths, dict):
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Invalid session")
            return
        lock = session["lock"]

        try:
            with lock:
                with open(str(paths[role]), "ab") as f:
                    f.write(data)
        except OSError as exc:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Cannot append chunk: {exc}")
            return

        self._send_json({"ok": True})

    def _finish_multi_recording_session(self) -> None:
        data = self._read_request_body()
        if data is None:
            return

        try:
            payload = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON")
            return

        session_id = str(payload.get("session_id", "")).strip()
        with self.server.sessions_lock:
            session = self.server.sessions.pop(session_id, None)
        if not session:
            self.send_error(HTTPStatus.NOT_FOUND, "Recording session not found")
            return

        try:
            result = self._finalize_multi_session(session, payload.get("metadata"))
        except (OSError, RuntimeError, ValueError) as exc:
            self._cleanup_session(session)
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Cannot save multi recording: {exc}")
            return

        self._cleanup_session(session)
        self._send_json(result)

    def _abort_multi_recording_session(self) -> None:
        data = self._read_request_body()
        if data is None:
            return
        try:
            payload = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError:
            payload = {}
        session_id = str(payload.get("session_id", "")).strip()
        with self.server.sessions_lock:
            session = self.server.sessions.pop(session_id, None)
        if session:
            self._cleanup_session(session)
        self._send_json({"ok": True})

    def _finalize_multi_session(self, session: dict[str, object], metadata_payload: object) -> dict[str, object]:
        metadata = metadata_payload if isinstance(metadata_payload, dict) else session.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        fps = int(metadata.get("fps") or 30)
        frame_count = int(metadata.get("frame_count") or 0)
        if fps <= 0 or frame_count <= 0:
            raise ValueError("Invalid fps or frame_count")

        save_dir = str(session["save_dir"])
        paths = session["paths"]
        if not isinstance(paths, dict):
            raise ValueError("Invalid session paths")

        role_sizes = {
            "head": (1280, 720),
            "left": (640, 360),
            "right": (640, 360),
        }
        for role in ("head", "left", "right"):
            if not os.path.exists(str(paths[role])) or os.path.getsize(str(paths[role])) <= 0:
                raise ValueError(f"Missing recording: {role}")

        with self.server.save_lock:
            index = next_multi_recording_index(save_dir)
            stem = f"{index:06d}"
            output_paths = {
                role: os.path.join(save_dir, role, f"{stem}.mp4")
                for role in ("head", "left", "right")
            }
            metadata_path = os.path.join(save_dir, "metadata", f"{stem}.json")

            for role, output_path in output_paths.items():
                convert_webm_file_to_mp4_file(str(paths[role]), output_path, role_sizes[role], fps, frame_count)

            metadata["mode"] = "multi"
            metadata["index"] = index
            metadata["fps"] = fps
            metadata["frame_count"] = frame_count
            metadata["duration_ms"] = round(frame_count * 1000 / fps)
            streams = metadata.get("streams")
            if not isinstance(streams, dict):
                streams = {}
            for role in ("head", "left", "right"):
                role_stream = streams.get(role)
                if not isinstance(role_stream, dict):
                    role_stream = {}
                role_stream["file"] = f"{role}/{stem}.mp4"
                role_stream["width"] = role_sizes[role][0]
                role_stream["height"] = role_sizes[role][1]
                role_stream["fps"] = fps
                role_stream["frame_count"] = frame_count
                streams[role] = role_stream
            metadata["streams"] = streams

            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
                f.write("\n")

        self.server.save_dir = save_dir
        response_files = {role: path for role, path in output_paths.items()}
        response_files["metadata"] = metadata_path
        return {"index": index, "files": response_files}

    def _cleanup_session(self, session: dict[str, object]) -> None:
        session_dir = str(session.get("dir", ""))
        if session_dir and os.path.isdir(session_dir):
            shutil.rmtree(session_dir, ignore_errors=True)

    def _convert_to_mp4(self) -> None:
        if not find_ffmpeg():
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "ffmpeg not found")
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid Content-Length")
            return

        if content_length <= 0:
            self.send_error(HTTPStatus.BAD_REQUEST, "Empty recording")
            return

        data = self.rfile.read(content_length)
        try:
            mp4_data = convert_webm_to_mp4(data)
        except RuntimeError as exc:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(len(mp4_data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(mp4_data)

    def _stream_server_camera(self) -> None:
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "ffmpeg not found")
            return

        args = self.server.args
        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "warning",
            "-f",
            "v4l2",
            "-framerate",
            str(args.framerate),
            "-video_size",
            args.size,
            "-i",
            args.device,
            "-an",
            "-f",
            "mpjpeg",
            "-boundary_tag",
            "frame",
            "pipe:1",
        ]

        self.send_response(HTTPStatus.OK)
        self.send_header("Age", "0")
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            assert proc.stdout is not None
            while True:
                chunk = proc.stdout.read(64 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Open a local web page for viewing a camera.")
    parser.add_argument("--host", default="127.0.0.1", help="bind address, default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=8765, help="preferred bind port, default: 8765")
    parser.add_argument("--no-auto-port", action="store_true", help="fail instead of trying the next port when --port is busy")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser automatically")
    parser.add_argument(
        "--server-camera",
        action="store_true",
        help="stream the Linux camera device from this machine with ffmpeg instead of using the browser camera API",
    )
    parser.add_argument("--device", default="/dev/video0", help="camera device for --server-camera")
    parser.add_argument("--size", default="1280x720", help="video size for --server-camera")
    parser.add_argument("--framerate", type=int, default=30, help="frame rate for --server-camera")
    parser.add_argument("--save-dir", default="~/Videos/camera_recordings", help="default directory for saved recordings")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.no_auto_port:
        args.port = find_available_port(args.host, args.port)

    os.makedirs(resolve_save_dir(args.save_dir), exist_ok=True)
    url_host = "localhost" if args.host in ("127.0.0.1", "0.0.0.0") else args.host
    url = f"http://{html.escape(url_host)}:{args.port}/"
    mode = "server camera" if args.server_camera else "browser camera"
    print(f"Serving {mode} page at {url}")
    print(f"Recordings will be saved under {resolve_save_dir(args.save_dir)}")
    print("Press Ctrl+C to stop.")
    with CameraServer((args.host, args.port), Handler, args) as httpd:
        if not args.no_browser:
            threading.Timer(0.6, lambda: webbrowser.open(url)).start()
        httpd.serve_forever()


if __name__ == "__main__":
    main()
