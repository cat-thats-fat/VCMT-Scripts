#!/usr/bin/env bash

mkdir -p ~/SharePoint/"Academics - VCMT"
mkdir -p ~/SharePoint/"Admin - VCMT"
mkdir -p ~/SharePoint/"Admission - VCMT"
mkdir -p ~/SharePoint/"Clinic - VCMT"
mkdir -p ~/SharePoint/"Documents - VCMT"
mkdir -p ~/SharePoint/"Surrey - VCMT"

rclone mount "VCMT Academics": ~/SharePoint/"Academics - VCMT" --daemon --vfs-cache-mode full --cache-dir ~/.cache/rclone
rclone mount "VCMT Admin": ~/SharePoint/"Admin - VCMT" --daemon --vfs-cache-mode full --cache-dir ~/.cache/rclone
rclone mount "VCMT Admission": ~/SharePoint/"Admission - VCMT" --daemon --vfs-cache-mode full --cache-dir ~/.cache/rclone
rclone mount "VCMT Clinic": ~/SharePoint/"Clinic - VCMT" --daemon --vfs-cache-mode full --cache-dir ~/.cache/rclone
rclone mount "VCMT Documents": ~/SharePoint/"Documents - VCMT" --daemon --vfs-cache-mode full --cache-dir ~/.cache/rclone
rclone mount "VCMT Surrey": ~/SharePoint/"Surrey - VCMT" --daemon --vfs-cache-mode full --cache-dir ~/.cache/rclone
