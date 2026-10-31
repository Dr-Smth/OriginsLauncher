import SwiftUI
import AppKit
import Foundation
import Darwin

private enum Palette {
    static let background = Color(red: 0.070, green: 0.075, blue: 0.083)
    static let card = Color(red: 0.105, green: 0.110, blue: 0.120)
    static let cream = Color(red: 0.94, green: 0.91, blue: 0.84)
    static let muted = Color(red: 0.62, green: 0.64, blue: 0.65)
    static let accent = Color(red: 0.647, green: 0.122, blue: 0.176)
    static let accentText = Color(red: 0.847, green: 0.353, blue: 0.392)
    static let line = Color.white.opacity(0.09)
}

private struct LauncherStatus: Decodable {
    var runtime_ready: Bool
    var prefix_ready: Bool
    var steam_installed: Bool
    var steam_running: Bool
    var game_installed: Bool
    var game_running: Bool
    var game_title: String?
    var game_appid: String?
    var game_dir: String?
    var storage_bytes: Int64
    var storage_measured_at: String?
    var compatibility_verified: Bool?
    var platform_supported: Bool?
    var rosetta_ready: Bool?
    var configuration_ready: Bool?
    var steam_maintenance_active: Bool?
    var steam_maintenance_message: String?
    var laa_supported: Bool?
    var laa_enabled: Bool?
    var laa_message: String?
    var audio_fix_supported: Bool?
    var audio_fix_enabled: Bool?
    var audio_fix_managed: Bool?
    var audio_fix_message: String?
    var console_supported: Bool?
    var console_enabled: Bool?
    var console_message: String?
    var phase: String
    var message: String
    var log_path: String
    var data_path: String
}

private struct DisplayDescription: Decodable {
    var name: String
    var logical_width: Int
    var logical_height: Int
    var pixel_width: Int
    var pixel_height: Int
    var refresh_rate: Double
    var scale: Double
}

private struct DisplayPreset: Decodable, Identifiable {
    var id: String
    var title: String
    var detail: String
    var width: Int
    var height: Int
    var fullscreen: Bool
    var retina: Bool
    var available: Bool
    var reason: String?
    var verification: String?
}

private struct CurrentDisplaySettings: Decodable {
    var width: Int?
    var height: Int?
    var fullscreen: Bool?
    var retina: Bool?
    var dpi: Int?
    var hud_scale: Double?
    var preset_id: String?
    var ui_size: String?
}

private struct DisplayOptions: Decodable {
    var ok: Bool
    var display: DisplayDescription?
    var presets: [DisplayPreset]
    var current: CurrentDisplaySettings?
    var can_apply: Bool
    var blocked_reason: String?
    var restore_available: Bool
    var can_restore: Bool?
    var restore_blocked_reason: String?
    var pending_confirmation: Bool
    var can_confirm: Bool?
    var ui_scaling_available: Bool
}

/// Bounded local lifecycle evidence. This accepts only typed metadata: never
/// helper arguments/output, account data, error text or user file paths.
private enum HelperTrace {
    enum Event: String {
        case requestCreated = "request_created", runStarted = "run_started"
        case launched, launchFailed = "launch_failed", launchDeclined = "launch_declined"
        case exitObserverAttached = "exit_observer_attached", exitNotice = "exit_notice_delivered"
        case completionCheckStarted = "completion_check_started", processExitConfirmed = "process_exit_confirmed"
        case waitCompleted = "wait_completed", timeout, terminateRequested = "terminate_requested"
        case killRequested = "kill_requested", cleanupWaitCompleted = "cleanup_wait_completed"
        case runReturned = "run_returned", mainActor = "main_actor_delivered"
        case uiApplied = "ui_applied", uiFailed = "ui_failed", uiSuperseded = "ui_superseded", uiOwnerGone = "ui_owner_gone"
    }
    struct Request: Sendable {
        let id = UUID().uuidString
        let command: String
        let generation: Int?
        init(_ command: String, generation: Int? = nil) {
            let allowed: Set<String> = ["status", "display-options", "setup", "steam", "stop", "play",
                "install-game", "configure-game", "install-ui-scaling", "diagnostics", "steam-maintain",
                "steam-maintenance-cancel", "display-apply", "display-confirm", "display-restore"]
            self.command = allowed.contains(command) ? command : "other"
            self.generation = generation
        }
    }
    struct Entry: Encodable {
        let schema = 1
        let session: String, request: String, command: String, event: String
        let monotonic_ns: UInt64
        let generation: Int?
        let pid: Int32?
        let status: Int32?
        let timed_out: Bool?
        let game_running: Bool?
        let dropped_before: UInt64
    }
    final class Writer: @unchecked Sendable {
        static let fileLimit = 1024 * 1024
        private let queue = DispatchQueue(label: "org.originslauncher.helper-trace", qos: .utility)
        private let slots = DispatchSemaphore(value: 128)
        private let lock = NSLock()
        private var dropped: UInt64 = 0
        private let session = UUID().uuidString
        private let library: URL?
        init(library: URL? = FileManager.default.urls(for: .libraryDirectory, in: .userDomainMask).first) {
            self.library = library
        }
        func record(_ request: Request, _ event: Event, pid: Int32?, status: Int32?, timedOut: Bool?, gameRunning: Bool?) {
            guard slots.wait(timeout: .now()) == .success else {
                lock.lock(); if dropped < UInt64.max { dropped += 1 }; lock.unlock()
                return
            }
            lock.lock(); let lost = dropped; dropped = 0; lock.unlock()
            let entry = Entry(session: session, request: request.id, command: request.command, event: event.rawValue,
                              monotonic_ns: DispatchTime.now().uptimeNanoseconds, generation: request.generation,
                              pid: pid, status: status, timed_out: timedOut, game_running: gameRunning, dropped_before: lost)
            queue.async {
                defer { self.slots.signal() }
                guard var data = try? JSONEncoder().encode(entry), data.count < 1024 else { return }
                data.append(10)
                self.append(data)
            }
        }
        // Only used by the isolated fixture; launch paths never wait for logs.
        func drain() { queue.sync {} }
        private func ownedRegular(_ fd: Int32) -> Bool {
            var info = stat()
            return fstat(fd, &info) == 0 && info.st_mode & S_IFMT == S_IFREG && info.st_uid == getuid()
                && info.st_nlink == 1 && info.st_mode & 0o777 == 0o600
        }
        private func append(_ data: Data) {
            guard let library else { return }
            let logs = library.appendingPathComponent("Logs", isDirectory: true).path
            guard mkdir(logs, 0o700) == 0 || errno == EEXIST else { return }
            let logsFD = open(logs, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)
            guard logsFD >= 0 else { return }; defer { close(logsFD) }
            guard mkdirat(logsFD, "OriginsLauncher", 0o700) == 0 || errno == EEXIST else { return }
            let directory = openat(logsFD, "OriginsLauncher", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)
            guard directory >= 0 else { return }; defer { close(directory) }
            var directoryInfo = stat()
            guard fstat(directory, &directoryInfo) == 0, directoryInfo.st_uid == getuid() else { return }
            var fd = openat(directory, "helper-events.jsonl", O_WRONLY | O_APPEND | O_CREAT | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC, 0o600)
            guard fd >= 0 else { return }; defer { close(fd) }
            guard ownedRegular(fd), flock(fd, LOCK_EX | LOCK_NB) == 0 else { return }
            var info = stat()
            guard fstat(fd, &info) == 0 else { return }
            if info.st_size + off_t(data.count) > off_t(Self.fileLimit) {
                let previous = openat(directory, "helper-events.previous.jsonl", O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC)
                if previous >= 0 {
                    let safe = ownedRegular(previous); close(previous)
                    guard safe else { return }
                } else if errno != ENOENT { return }
                guard renameat(directory, "helper-events.jsonl", directory, "helper-events.previous.jsonl") == 0 else { return }
                close(fd)
                fd = openat(directory, "helper-events.jsonl", O_WRONLY | O_APPEND | O_CREAT | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC, 0o600)
                guard fd >= 0, ownedRegular(fd), flock(fd, LOCK_EX | LOCK_NB) == 0 else { return }
            }
            _ = data.withUnsafeBytes { bytes in Darwin.write(fd, bytes.baseAddress, bytes.count) }
        }
    }
    private static let writer = Writer()
    static let observerQueue = DispatchQueue(label: "org.originslauncher.helper-exit", qos: .utility)
    static func request(_ command: String, generation: Int? = nil) -> Request {
        let request = Request(command, generation: generation)
        record(request, .requestCreated)
        return request
    }
    static func record(_ request: Request, _ event: Event, pid: Int32? = nil, status: Int32? = nil,
                       timedOut: Bool? = nil, gameRunning: Bool? = nil) {
        writer.record(request, event, pid: pid, status: status, timedOut: timedOut, gameRunning: gameRunning)
    }
}

private struct CommandResult {
    let status: Int32
    let output: Data
    let error: String
    let timedOut: Bool
    let trace: HelperTrace.Request
}

/// Run the bundled controller without a shell. Files avoid pipe-buffer deadlocks
/// when a long-running setup command or a child process writes substantial output.
/// One identity per native-app lifetime. A different launch cannot resume an
/// earlier startup flow, and close-time cancellation only targets this owner.
private final class LauncherLifetime: @unchecked Sendable {
    static let shared = LauncherLifetime()
    let session = UUID().uuidString
    private let lock = NSLock()
    private var closing = false
    private var maintenance: Process?
    private var startupRequested = false

    func launch(_ process: Process, command: String) throws -> Bool {
        lock.lock()
        defer { lock.unlock() }
        guard !closing || command == "steam-maintenance-cancel" else { return false }
        try process.run()
        if command == "setup" || command == "steam" { startupRequested = true }
        if command == "steam-maintain" { maintenance = process }
        return true
    }

    func finished(_ process: Process) {
        lock.lock()
        defer { lock.unlock() }
        if maintenance === process { maintenance = nil }
    }

    func beginShutdown() -> (maintenance: Process?, cancelStartup: Bool) {
        lock.lock()
        defer { lock.unlock() }
        closing = true
        let process = maintenance
        if let process, process.isRunning { process.terminate() }
        return (process, startupRequested || process != nil)
    }
}

private enum Controller {
    /// Foundation can know that the child exited while a waitUntilExit run loop
    /// remains asleep. Recheck its state at most every 100 ms on this worker;
    /// an exit notification is only a wakeup hint, never the source of truth.
    /// No extra waiting thread or dependency on a termination callback remains.
    static func waitForExit(_ process: Process, until deadline: DispatchTime, wake: DispatchSemaphore) -> Bool {
        while process.isRunning {
            let now = DispatchTime.now()
            if now >= deadline { return !process.isRunning }
            _ = wake.wait(timeout: min(deadline, now + .milliseconds(100)))
        }
        return true
    }

    static func run(_ arguments: [String], timeout: TimeInterval, trace suppliedTrace: HelperTrace.Request? = nil) -> CommandResult {
        let trace = suppliedTrace ?? HelperTrace.request(arguments.first ?? "other")
        HelperTrace.record(trace, .runStarted)
        func result(status: Int32, output: Data, error: String, timedOut: Bool) -> CommandResult {
            HelperTrace.record(trace, .runReturned, status: status, timedOut: timedOut)
            return CommandResult(status: status, output: output, error: error, timedOut: timedOut, trace: trace)
        }
        guard let script = Bundle.main.url(forResource: "daoctl", withExtension: "py") else {
            return result(status: 1, output: Data(), error: "The bundled controller is missing. Rebuild or restore the launcher app.", timedOut: false)
        }
        guard let resources = Bundle.main.resourceURL else {
            return result(status: 1, output: Data(), error: "The app’s resources are missing. Download a complete copy of Origins Launcher.", timedOut: false)
        }
        let python = resources.appendingPathComponent("python/bin/python3")
        guard FileManager.default.isExecutableFile(atPath: python.path) else {
            return result(status: 1, output: Data(), error: "The app’s bundled helper is missing or damaged. Download a complete copy of Origins Launcher; no separate Python installation is needed.", timedOut: false)
        }
        guard let support = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first else {
            return result(status: 1, output: Data(), error: "Your Application Support folder could not be located.", timedOut: false)
        }
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent("origins-command-" + UUID().uuidString)
        do {
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            defer { try? FileManager.default.removeItem(at: directory) }
            let outURL = directory.appendingPathComponent("stdout")
            let errURL = directory.appendingPathComponent("stderr")
            FileManager.default.createFile(atPath: outURL.path, contents: nil, attributes: [.posixPermissions: 0o600])
            FileManager.default.createFile(atPath: errURL.path, contents: nil, attributes: [.posixPermissions: 0o600])
            let outHandle = try FileHandle(forWritingTo: outURL)
            let errHandle = try FileHandle(forWritingTo: errURL)
            defer { try? outHandle.close(); try? errHandle.close() }
            let process = Process()
            process.executableURL = python
            process.arguments = ["-B", script.path] + arguments
            var environment = ProcessInfo.processInfo.environment
            // The release app owns a separate per-user environment. Never inherit
            // a development prefix or import paths from the launching terminal.
            environment["DAO_PROJECT_ROOT"] = support.appendingPathComponent("OriginsLauncher", isDirectory: true).path
            environment["DAO_LAUNCHER_SESSION"] = LauncherLifetime.shared.session
            environment.removeValue(forKey: "PYTHONHOME")
            environment.removeValue(forKey: "PYTHONPATH")
            environment["PYTHONNOUSERSITE"] = "1"
            if FileManager.default.isReadableFile(atPath: "/etc/ssl/cert.pem") {
                environment["SSL_CERT_FILE"] = "/etc/ssl/cert.pem"
            }
            environment["PYTHONIOENCODING"] = "utf-8"
            environment["PYTHONUNBUFFERED"] = "1"
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            process.environment = environment
            process.standardInput = FileHandle.nullDevice
            process.standardOutput = outHandle
            process.standardError = errHandle
            let exitWake = DispatchSemaphore(value: 0)
            guard try LauncherLifetime.shared.launch(process, command: arguments.first ?? "") else {
                HelperTrace.record(trace, .launchDeclined)
                return result(status: 130, output: Data(), error: "The launcher is closing.", timedOut: false)
            }
            defer { LauncherLifetime.shared.finished(process) }
            let pid = process.processIdentifier
            HelperTrace.record(trace, .launched, pid: pid)
            // This notification is independent of Foundation's waiter. Its
            // delivery time is an observation, not the exact kernel exit time;
            // a very short-lived helper may exit before the observer attaches.
            let exitObserver = DispatchSource.makeProcessSource(identifier: pid, eventMask: .exit, queue: HelperTrace.observerQueue)
            exitObserver.setEventHandler {
                HelperTrace.record(trace, .exitNotice, pid: pid)
                exitWake.signal()
            }
            exitObserver.activate()
            HelperTrace.record(trace, .exitObserverAttached, pid: pid)
            defer { exitObserver.cancel() }
            HelperTrace.record(trace, .completionCheckStarted, pid: pid)
            let timedOut = !waitForExit(process, until: .now() + timeout, wake: exitWake)
            HelperTrace.record(trace, timedOut ? .timeout : .waitCompleted, pid: pid, timedOut: timedOut)
            if timedOut {
                if process.isRunning {
                    HelperTrace.record(trace, .terminateRequested, pid: pid)
                    process.terminate()
                }
                let cleanupTimedOut = !waitForExit(process, until: .now() + 3, wake: exitWake)
                HelperTrace.record(trace, .cleanupWaitCompleted, pid: pid, timedOut: cleanupTimedOut)
                if cleanupTimedOut, process.isRunning {
                    HelperTrace.record(trace, .killRequested, pid: pid)
                    kill(process.processIdentifier, SIGKILL)
                    let killTimedOut = !waitForExit(process, until: .now() + 3, wake: exitWake)
                    HelperTrace.record(trace, .cleanupWaitCompleted, pid: pid, timedOut: killTimedOut)
                }
            }
            if !process.isRunning {
                HelperTrace.record(trace, .processExitConfirmed, pid: pid, status: process.terminationStatus)
            }
            try? outHandle.synchronize()
            try? errHandle.synchronize()
            let output = (try? Data(contentsOf: outURL)) ?? Data()
            let error = (try? String(contentsOf: errURL, encoding: .utf8)) ?? ""
            return result(status: timedOut ? 124 : process.terminationStatus, output: output, error: error, timedOut: timedOut)
        } catch {
            HelperTrace.record(trace, .launchFailed)
            return result(status: 1, output: Data(), error: error.localizedDescription, timedOut: false)
        }
    }

    static func object(_ data: Data) -> [String: Any]? {
        if let value = try? JSONSerialization.jsonObject(with: data) as? [String: Any] { return value }
        // Permit progress messages before a final JSON response.
        let lines = String(data: data, encoding: .utf8)?.split(separator: "\n") ?? []
        for line in lines.reversed() {
            if let value = try? JSONSerialization.jsonObject(with: Data(line.utf8)) as? [String: Any] { return value }
        }
        return nil
    }

    static func failure(_ result: CommandResult) -> String {
        if result.timedOut {
            return "This operation took too long. A Steam or setup window may still be open. Check that window, then refresh or create a diagnostic report before trying again."
        }
        if let message = object(result.output)?["message"] as? String { return message }
        let error = result.error.trimmingCharacters(in: .whitespacesAndNewlines)
        return error.isEmpty ? "The controller did not return a valid response. Open the logs for details." : String(error.suffix(700))
    }
}

@MainActor
private final class LauncherModel: ObservableObject {
    @Published var status: LauncherStatus?
    @Published var busy = false
    @Published var busyLabel = ""
    @Published var refreshing = false
    @Published var notification = ""
    @Published var isError = false
    @Published var statusFetchError = ""
    @Published var steamMaintenanceMessage = ""
    @Published var steamMaintenanceIsError = false
    @Published var edition = "47810"
    @Published var showStopConfirmation = false
    @Published var displayOptions: DisplayOptions?
    @Published var displayLoading = false
    @Published var displayMessage = ""
    @Published var displayIsError = false
    @Published var selectedPresetID = ""
    @Published var selectedUISize = "comfortable"
    @Published var selectedDisplayMode = "fullscreen"
    @Published private(set) var selectedLargeAddressAware = false
    @Published private(set) var selectedDeveloperConsole = false
    private var developerConsolePreferenceChosen = false
    private var statusRequest = 0
    private var displayRequest = 0
    private var displayFetchFailed = false
    private var displayDefaultsChosen = false
    private let displayPreferenceKey = "display-selection-v1"
    private let largeAddressPreferenceKey = "large-address-aware-v1"
    private let developerConsolePreferenceKey = "developer-console-v1"
    private var timer: Timer?
    private var lastSteamMaintenanceStarted: Date?

    init() {
        // Only an explicit choice saved by this UI opts in. A runtime already
        // modified elsewhere must not silently enable the user's selection.
        selectedLargeAddressAware = UserDefaults.standard.object(forKey: largeAddressPreferenceKey) as? Bool ?? false
        if let saved = UserDefaults.standard.object(forKey: developerConsolePreferenceKey) as? Bool {
            selectedDeveloperConsole = saved
            developerConsolePreferenceChosen = true
        }
        timer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self else { return }
                let visible = NSApp.windows.contains(where: { $0.isVisible && !$0.isMiniaturized })
                // Only an explicitly armed backend startup flow keeps polling
                // while minimized. Closing the app ends this timer entirely.
                guard visible || self.steamMaintenanceActive else { return }
                self.refresh()
                if visible && self.displaySettingsReady { self.loadDisplayOptions() }
            }
        }
    }

    var hasSession: Bool { steamMaintenanceActive || status?.steam_running == true || status?.game_running == true }
    var steamMaintenanceActive: Bool { status?.steam_maintenance_active == true }
    var prefixReady: Bool { status?.prefix_ready == true && status?.phase != "prefix_containment_required" }
    var configurationRequired: Bool {
        prefixReady && status?.game_installed == true && (status?.configuration_ready == false || ["game_configuration_required", "game_configuration_running"].contains(status?.phase ?? ""))
    }
    var displaySettingsReady: Bool { platformReady && prefixReady && status?.game_installed == true && !configurationRequired }
    var platformReady: Bool { status?.platform_supported != false && status?.rosetta_ready != false }
    var needsSetup: Bool { status != nil && (status?.runtime_ready != true || !prefixReady || status?.steam_installed != true || !platformReady) }
    var gameArguments: [String] { status?.game_appid.map { ["--appid", $0] } ?? [] }
    var gameplayHint: String {
        guard status?.game_installed == true else {
            return "Sign in and download your owned copy in the Steam window."
        }
        return status?.compatibility_verified == true
            ? "Use Play to launch your installed copy."
            : "Launch the game to test gameplay, audio, and save/load on this Mac."
    }
    var steamIsPreparing: Bool { ["steam_updating", "steam_starting", "steam_handoff_wait"].contains(status?.phase ?? "") }
    var steamDetail: String {
        switch status?.phase {
        case "steam_installing": return "Installer open"
        case "steam_handoff_wait": return "Continuing startup"
        case "steam_startup_blocked": return "Startup paused"
        case "steam_updating": return "Updating client"
        case "steam_starting": return "Starting client"
        case "steam_restart_required": return "Restart needed"
        default:
            return status?.steam_installed == true ? (status?.steam_running == true ? "Running" : "Installed") : "Preparation needed"
        }
    }
    var storage: String {
        guard let status else { return "Storage not measured yet" }
        guard status.storage_bytes > 0 else { return "Storage measurement pending" }
        return ByteCountFormatter.string(fromByteCount: status.storage_bytes, countStyle: .file) + " · cached storage measurement"
    }
    var storageHelp: String {
        let timestamp = status?.storage_measured_at.map { " Last measured: \($0)." } ?? ""
        return "Storage is measured during setup and when you create a diagnostic report; it is not a live total.\(timestamp) Use Diagnostics to refresh it."
    }
    var heading: String {
        guard let status else { return "Checking your setup" }
        if status.phase == "prefix_containment_required" { return "Finish environment setup" }
        if status.game_running { return "Your adventure is running" }
        switch status.phase {
        case "unsupported_platform": return "This Mac is not supported"
        case "rosetta_required": return "Rosetta is required"
        case "runtime_missing": return "Ready to set up"
        case "game_configuration_required": return "Finish game setup"
        case "game_configuration_running": return "Complete the game setup window"
        case "steam_installing": return "Complete Steam setup"
        case "steam_handoff_wait": return "Continuing Steam setup"
        case "steam_startup_blocked": return "Steam startup paused"
        case "steam_updating": return "Steam is updating"
        case "steam_starting": return "Steam is starting"
        case "steam_restart_required": return "Steam needs a restart"
        case "downloading": return "Downloading your game"
        default: break
        }
        if status.game_installed { return "Ready to launch" }
        if status.steam_installed { return "Sign in and download your game" }
        return "Prepare your game environment"
    }

    func refresh(allowSteamMaintenance: Bool = true) {
        guard !refreshing, !busy else { return }
        refreshing = true
        statusRequest += 1
        let request = statusRequest
        let trace = HelperTrace.request("status", generation: request)
        DispatchQueue.global(qos: .utility).async { [weak self] in
            let result = Controller.run(["status"], timeout: 25, trace: trace)
            let object = Controller.object(result.output)
            let normalized = object.flatMap { try? JSONSerialization.data(withJSONObject: $0) }
            let status = normalized.flatMap { try? JSONDecoder().decode(LauncherStatus.self, from: $0) }
            Task { @MainActor in
                HelperTrace.record(trace, .mainActor, status: result.status, gameRunning: status?.game_running)
                guard let self else { HelperTrace.record(trace, .uiOwnerGone); return }
                guard request == self.statusRequest else {
                    HelperTrace.record(trace, .uiSuperseded, gameRunning: status?.game_running); return
                }
                self.refreshing = false
                if result.status == 0, let status {
                    self.status = status
                    HelperTrace.record(trace, .uiApplied, gameRunning: status.game_running)
                    if !self.developerConsolePreferenceChosen {
                        self.selectedDeveloperConsole = status.console_enabled == true
                    }
                    self.statusFetchError = ""
                    if !self.steamMaintenanceIsError {
                        self.steamMaintenanceMessage = ""
                    }
                    if allowSteamMaintenance { self.maintainSteam(after: status) }
                    if self.displaySettingsReady && self.displayOptions == nil { self.loadDisplayOptions() }
                } else {
                    HelperTrace.record(trace, .uiFailed, status: result.status, timedOut: result.timedOut)
                    self.status?.compatibility_verified = false
                    self.statusFetchError = Controller.failure(result)
                }
            }
        }
    }

    private func maintainSteam(after snapshot: LauncherStatus) {
        // Status remains read-only. Only a fresh, backend-armed snapshot can
        // request this separately locked action; readiness also gets one call
        // so the backend can persistently disarm the completed generation.
        guard snapshot.steam_maintenance_active == true, !busy, !showStopConfirmation else { return }
        if let previous = lastSteamMaintenanceStarted, Date().timeIntervalSince(previous) < 4 { return }
        lastSteamMaintenanceStarted = Date()
        busy = true
        busyLabel = "Continuing Steam startup…"
        statusRequest += 1
        refreshing = false
        displayRequest += 1
        displayLoading = false
        let trace = HelperTrace.request("steam-maintain")
        DispatchQueue.global(qos: .utility).async { [weak self] in
            let result = Controller.run(["steam-maintain"], timeout: 180, trace: trace)
            let payload = Controller.object(result.output)
            Task { @MainActor in
                HelperTrace.record(trace, .mainActor, status: result.status)
                guard let self else { HelperTrace.record(trace, .uiOwnerGone); return }
                self.busy = false
                self.busyLabel = ""
                let success = result.status == 0 && payload?["ok"] as? Bool == true
                HelperTrace.record(trace, success ? .uiApplied : .uiFailed, status: result.status, timedOut: result.timedOut)
                if success {
                    if let active = payload?["steam_maintenance_active"] as? Bool {
                        self.status?.steam_maintenance_active = active
                    }
                    let action = payload?["action"] as? String
                    self.steamMaintenanceIsError = action == "blocked"
                    self.steamMaintenanceMessage = payload?["message"] as? String ?? ""
                } else {
                    self.steamMaintenanceIsError = true
                    self.steamMaintenanceMessage = Controller.failure(result)
                }
                // Avoid a status → maintain → status loop. The normal timer
                // supplies the next fresh observation, including while minimized.
                self.refresh(allowSteamMaintenance: false)
            }
        }
    }

    var selectedDisplayPreset: DisplayPreset? {
        displayOptions?.presets.first(where: { $0.id == selectedPresetID })
    }
    var visibleDisplayPresets: [DisplayPreset] {
        displayOptions?.presets.filter { $0.fullscreen == (selectedDisplayMode == "fullscreen") } ?? []
    }
    var canPlayWithDisplaySelection: Bool {
        platformReady && displaySettingsReady && displayOptions != nil && selectedDisplayPreset?.available == true &&
            selectedDisplayPreset?.fullscreen == (selectedDisplayMode == "fullscreen")
    }
    var playArguments: [String] {
        var arguments = ["--preset", selectedPresetID, "--ui-size", selectedUISize,
         "--large-address-aware", selectedLargeAddressAware ? "on" : "off"]
        // No saved choice leaves a manually configured console untouched.
        if developerConsolePreferenceChosen {
            arguments += ["--developer-console", selectedDeveloperConsole ? "on" : "off"]
        }
        return arguments
    }
    var canChangeLargeAddressAware: Bool {
        displaySettingsReady && status?.runtime_ready == true && !busy &&
            status?.game_running != true && statusFetchError.isEmpty &&
            (status?.laa_supported == true || selectedLargeAddressAware)
    }
    func chooseLargeAddressAware(_ enabled: Bool) {
        guard canChangeLargeAddressAware, !enabled || status?.laa_supported == true else { return }
        selectedLargeAddressAware = enabled
        UserDefaults.standard.set(enabled, forKey: largeAddressPreferenceKey)
    }
    var canChangeDeveloperConsole: Bool {
        displaySettingsReady && !busy && status?.game_running != true && statusFetchError.isEmpty &&
            (status?.console_supported == true || selectedDeveloperConsole)
    }
    func chooseDeveloperConsole(_ enabled: Bool) {
        guard canChangeDeveloperConsole, !enabled || status?.console_supported == true else { return }
        selectedDeveloperConsole = enabled
        developerConsolePreferenceChosen = true
        UserDefaults.standard.set(enabled, forKey: developerConsolePreferenceKey)
    }
    private func persistDisplaySelection() {
        guard canPlayWithDisplaySelection else { return }
        UserDefaults.standard.set(["preset_id": selectedPresetID, "mode": selectedDisplayMode, "ui_size": selectedUISize], forKey: displayPreferenceKey)
    }
    func chooseDisplayPreset(_ id: String) {
        guard let preset = displayOptions?.presets.first(where: { $0.id == id && $0.available }) else { return }
        selectedPresetID = preset.id
        selectedDisplayMode = preset.fullscreen ? "fullscreen" : "windowed"
        persistDisplaySelection()
    }
    func chooseDisplayMode(_ mode: String) {
        guard ["fullscreen", "windowed"].contains(mode) else { return }
        selectedDisplayMode = mode
        if selectedDisplayPreset?.fullscreen != (mode == "fullscreen") {
            let preferredID = mode == "fullscreen" ? "fullscreen-retina" : ""
            selectedPresetID = visibleDisplayPresets.first(where: { $0.available && $0.id == preferredID })?.id ??
                visibleDisplayPresets.first(where: { $0.available })?.id ?? ""
        }
        persistDisplaySelection()
    }
    func chooseUISize(_ size: String) {
        guard ["comfortable", "larger"].contains(size) else { return }
        selectedUISize = size
        persistDisplaySelection()
    }

    func loadDisplayOptions() {
        guard displaySettingsReady, !displayLoading, !busy else { return }
        displayLoading = true
        displayRequest += 1
        let request = displayRequest
        let trace = HelperTrace.request("display-options", generation: request)
        DispatchQueue.global(qos: .utility).async { [weak self] in
            let result = Controller.run(["display-options"], timeout: 25, trace: trace)
            let object = Controller.object(result.output)
            let data = object.flatMap { try? JSONSerialization.data(withJSONObject: $0) }
            let options = data.flatMap { try? JSONDecoder().decode(DisplayOptions.self, from: $0) }
            Task { @MainActor in
                HelperTrace.record(trace, .mainActor, status: result.status)
                guard let self else { HelperTrace.record(trace, .uiOwnerGone); return }
                guard request == self.displayRequest else { HelperTrace.record(trace, .uiSuperseded); return }
                self.displayLoading = false
                if result.status == 0, let options, options.ok {
                    HelperTrace.record(trace, .uiApplied)
                    self.displayOptions = options
                    let selectedStillAvailable = options.presets.contains(where: { $0.id == self.selectedPresetID && $0.available })
                    if !self.displayDefaultsChosen || !selectedStillAvailable {
                        let saved = !self.displayDefaultsChosen ? UserDefaults.standard.dictionary(forKey: self.displayPreferenceKey) : nil
                        let savedID = saved?["preset_id"] as? String
                        let savedPreset = options.presets.first(where: { $0.available && $0.id == savedID })
                        let native = options.presets.first(where: { $0.available && $0.id == "fullscreen-retina" }) ??
                            options.presets.first(where: { $0.available && $0.id == "fullscreen" }) ??
                            options.presets.first(where: { $0.available })
                        let chosen = savedPreset ?? native
                        self.selectedPresetID = chosen?.id ?? ""
                        self.selectedDisplayMode = chosen?.fullscreen == false ? "windowed" : "fullscreen"
                        if !self.displayDefaultsChosen {
                            let savedSize = saved?["ui_size"] as? String ?? "comfortable"
                            self.selectedUISize = ["comfortable", "larger"].contains(savedSize) ? savedSize : "comfortable"
                        }
                        self.displayDefaultsChosen = true
                    }
                    if !options.ui_scaling_available {
                        self.selectedUISize = "comfortable"
                    }
                    if self.displayFetchFailed {
                        self.displayMessage = ""
                        self.displayIsError = false
                        self.displayFetchFailed = false
                    }
                } else {
                    HelperTrace.record(trace, .uiFailed, status: result.status, timedOut: result.timedOut)
                    self.displayFetchFailed = true
                    self.displayOptions = nil
                    self.displayMessage = Controller.failure(result)
                    self.displayIsError = true
                }
            }
        }
    }

    func run(_ command: String, label: String, arguments: [String] = []) {
        guard !busy else { return }
        if command == "play" {
            guard canPlayWithDisplaySelection else {
                notification = "Choose an available display preset before playing."
                isError = true
                return
            }
            guard !selectedLargeAddressAware || status?.laa_supported == true else {
                notification = status?.laa_message ?? "4 GB memory support is unavailable for this runtime. Turn it off to use the normal memory limit."
                isError = true
                return
            }
            guard !developerConsolePreferenceChosen || !selectedDeveloperConsole || status?.console_supported == true else {
                notification = status?.console_message ?? "Developer console is unavailable for this installation."
                isError = true
                return
            }
            persistDisplaySelection()
        }
        busy = true
        busyLabel = label
        if ["setup", "steam", "stop", "play", "install-game"].contains(command) {
            steamMaintenanceMessage = ""
            steamMaintenanceIsError = false
        }
        // Ignore already-running read-only requests once an action starts.
        // Future timer polls remain paused until that action completes.
        statusRequest += 1
        refreshing = false
        displayRequest += 1
        displayLoading = false
        displayMessage = ""
        displayIsError = false
        displayFetchFailed = false
        notification = command == "setup" ? "Downloading and preparing the runtime and Steam. This can take several minutes. Keep Origins Launcher open and follow any installer windows that appear." : ""
        isError = false
        let trace = HelperTrace.request(command)
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let result = Controller.run([command] + arguments, timeout: ["setup", "configure-game", "install-ui-scaling"].contains(command) ? 1800 : ((command == "play" || command.hasPrefix("display-")) ? 360 : 180), trace: trace)
            let payload = Controller.object(result.output)
            Task { @MainActor in
                HelperTrace.record(trace, .mainActor, status: result.status)
                guard let self else { HelperTrace.record(trace, .uiOwnerGone); return }
                self.busy = false
                self.busyLabel = ""
                let success = result.status == 0 && payload?["ok"] as? Bool != false
                HelperTrace.record(trace, success ? .uiApplied : .uiFailed, status: result.status, timedOut: result.timedOut)
                self.isError = !success
                if success {
                    self.notification = command == "play" ? "" : (payload?["message"] as? String ?? "Operation completed.")
                    if command == "diagnostics" {
                        if let path = (payload?["report_path"] ?? payload?["path"]) as? String {
                            self.reveal(path)
                        } else if let raw = String(data: result.output, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines), raw.hasPrefix("/") {
                            self.reveal(raw)
                        }
                    }
                } else {
                    self.notification = Controller.failure(result)
                }
                if command.hasPrefix("display-") {
                    self.displayMessage = self.notification
                    self.displayIsError = !success
                }
                self.refresh()
                if self.displaySettingsReady { self.loadDisplayOptions() }
            }
        }
    }

    var rosettaInstallerURL: URL {
        URL(fileURLWithPath: "/System/Library/CoreServices/Rosetta 2 Updater.app", isDirectory: true)
    }

    func openRosettaInstaller() {
        guard status?.phase == "rosetta_required", !busy else { return }
        guard FileManager.default.fileExists(atPath: rosettaInstallerURL.path) else {
            notification = "Apple’s Rosetta installer was not found. Use the Apple Rosetta help link, then refresh this launcher."
            isError = true
            return
        }
        NSWorkspace.shared.openApplication(at: rosettaInstallerURL, configuration: NSWorkspace.OpenConfiguration()) { [weak self] _, error in
            Task { @MainActor in
                guard let self else { return }
                self.isError = error != nil
                self.notification = error.map { "Apple’s Rosetta installer could not open: " + $0.localizedDescription }
                    ?? "Complete the Apple Rosetta installer’s prompts, then choose Refresh."
            }
        }
    }

    func reveal(_ path: String) {
        let url = URL(fileURLWithPath: path)
        if FileManager.default.fileExists(atPath: url.path) {
            NSWorkspace.shared.activateFileViewerSelecting([url])
        } else if FileManager.default.fileExists(atPath: url.deletingLastPathComponent().path) {
            NSWorkspace.shared.open(url.deletingLastPathComponent())
        } else {
            notification = "This folder will be created when the game environment is prepared."
            isError = false
        }
    }
}

private struct PrimaryButton: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 13, weight: .semibold))
            .frame(maxWidth: .infinity)
            .padding(.vertical, 12)
            .foregroundStyle(Palette.cream)
            .background(Palette.accent.opacity(configuration.isPressed ? 0.78 : 1))
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .opacity(configuration.isPressed ? 0.9 : 1)
    }
}

private struct QuietButton: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 12, weight: .medium))
            .padding(.horizontal, 12).padding(.vertical, 9)
            .foregroundStyle(Palette.cream)
            .background(Color.white.opacity(configuration.isPressed ? 0.12 : 0.055))
            .clipShape(RoundedRectangle(cornerRadius: 7))
            .overlay(RoundedRectangle(cornerRadius: 7).stroke(Palette.line))
    }
}

private struct StatusRow: View {
    let title: String
    let detail: String
    let ready: Bool
    var body: some View {
        HStack(spacing: 11) {
            Image(systemName: ready ? "checkmark.circle.fill" : "circle")
                .foregroundStyle(ready ? Palette.accent : Palette.muted.opacity(0.6))
                .font(.system(size: 15))
                .accessibilityHidden(true)
            Text(title).font(.system(size: 12, weight: .medium)).foregroundStyle(Palette.cream)
            Spacer()
            Text(detail).font(.system(size: 11)).foregroundStyle(Palette.muted)
        }
        .accessibilityElement(children: .combine)
    }
}

private enum BrandAssets {
    static let logo: NSImage? = Bundle.main.url(forResource: "DragonAgeOrigins", withExtension: "icns")
        .flatMap { NSImage(contentsOf: $0) }
}

private struct DisplaySettingsPanel: View {
    @ObservedObject var model: LauncherModel

    private func presetLabel(_ preset: DisplayPreset) -> String {
        let dimensions = "\(preset.width) × \(preset.height)"
        let isNative = preset.fullscreen && preset.width == model.displayOptions?.display?.pixel_width && preset.height == model.displayOptions?.display?.pixel_height
        let title = isNative ? "Native · \(dimensions)" : (preset.fullscreen ? "Performance · \(dimensions)" : dimensions)
        return preset.available ? title : title + " — " + (preset.reason ?? "Unavailable on this display")
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 13) {
            HStack {
                Label("Display & interface", systemImage: "display")
                    .font(.system(size: 15, weight: .semibold)).foregroundStyle(Palette.cream)
                Spacer()
                if model.displayLoading && model.displayOptions == nil {
                    ProgressView().controlSize(.small).scaleEffect(0.8).accessibilityLabel("Reading display settings")
                }
                Button { model.loadDisplayOptions() } label: { Image(systemName: "arrow.clockwise") }
                    .buttonStyle(.plain).foregroundStyle(Palette.muted).help("Refresh connected displays").accessibilityLabel("Refresh connected displays")
                    .disabled(model.busy || model.displayLoading)
            }
            if let options = model.displayOptions {
                if let display = options.display {
                    Text("\(display.name) · \(display.pixel_width) × \(display.pixel_height) pixels" + (display.refresh_rate > 0 ? " · \(Int(display.refresh_rate.rounded())) Hz" : ""))
                        .font(.system(size: 11)).foregroundStyle(Palette.muted)
                }
                GeometryReader { geometry in
                    let columnWidth = (geometry.size.width - 24) / 3
                    HStack(alignment: .top, spacing: 12) {
                        VStack(alignment: .leading, spacing: 6) {
                            Text("Mode").font(.system(size: 11, weight: .semibold)).foregroundStyle(Palette.cream)
                            Picker("Display mode", selection: Binding(get: { model.selectedDisplayMode }, set: { model.chooseDisplayMode($0) })) {
                                Text("Full screen").tag("fullscreen")
                                Text("Windowed").tag("windowed")
                            }.pickerStyle(.segmented).labelsHidden().disabled(model.busy)
                        }.frame(width: columnWidth, alignment: .leading)
                        VStack(alignment: .leading, spacing: 6) {
                            Text("UI size").font(.system(size: 11, weight: .semibold)).foregroundStyle(Palette.cream)
                            Picker("UI size", selection: Binding(get: { model.selectedUISize }, set: { model.chooseUISize($0) })) {
                                Text("Comfortable").tag("comfortable")
                                Text("Larger").tag("larger")
                            }.pickerStyle(.segmented).labelsHidden().disabled(model.busy || !options.ui_scaling_available)
                        }.frame(width: columnWidth, alignment: .leading)
                        VStack(alignment: .leading, spacing: 6) {
                            Text("Resolution").font(.system(size: 11, weight: .semibold)).foregroundStyle(Palette.cream)
                            Picker("Resolution", selection: Binding(get: { model.selectedPresetID }, set: { model.chooseDisplayPreset($0) })) {
                                if model.visibleDisplayPresets.isEmpty || model.selectedPresetID.isEmpty {
                                    Text("No available resolution").tag("").disabled(true)
                                }
                                ForEach(model.visibleDisplayPresets) { preset in
                                    Text(presetLabel(preset)).tag(preset.id).disabled(!preset.available)
                                }
                            }.pickerStyle(.menu).labelsHidden().frame(maxWidth: .infinity).disabled(model.busy)
                        }.frame(width: columnWidth, alignment: .leading)
                    }.font(.system(size: 12))
                }.frame(height: 49)
                if !options.ui_scaling_available {
                    VStack(alignment: .leading, spacing: 9) {
                        Text("Optional UI scaling adds the DAFix mod for a larger, readable interface and Retina display presets. It is downloaded only when you enable it.")
                            .font(.system(size: 11)).foregroundStyle(Palette.muted).fixedSize(horizontal: false, vertical: true)
                        HStack(spacing: 12) {
                            Button("Enable UI scaling") {
                                model.run("install-ui-scaling", label: "Installing optional UI scaling…", arguments: model.gameArguments)
                            }.buttonStyle(QuietButton()).disabled(model.busy || !model.platformReady || model.status?.game_running == true)
                            Link("DAFix release & license", destination: URL(string: "https://github.com/Lyall/DAFix/releases/tag/v0.0.3")!)
                                .font(.system(size: 11)).foregroundStyle(Palette.accentText)
                        }
                    }.padding(.top, 3)
                }
            } else if model.displayLoading {
                Text("Reading your display and available resolutions…").font(.system(size: 12)).foregroundStyle(Palette.muted).padding(.vertical, 8)
            } else if model.displayMessage.isEmpty {
                Text("Display settings are not available yet. Refresh to try again.").font(.system(size: 12)).foregroundStyle(Palette.muted)
            }
            if !model.displayMessage.isEmpty {
                Label(model.displayMessage, systemImage: model.displayIsError ? "exclamationmark.triangle" : "info.circle")
                    .font(.system(size: 11)).foregroundStyle(model.displayIsError ? Palette.accentText : Palette.muted)
                    .textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
            }
            Rectangle().fill(Palette.line).frame(height: 1)
            HStack(spacing: 24) {
                Toggle(isOn: Binding(get: { model.selectedLargeAddressAware }, set: { model.chooseLargeAddressAware($0) })) {
                    Text("4 GB memory support · Experimental")
                        .font(.system(size: 12, weight: .semibold)).foregroundStyle(Palette.cream)
                }
                .toggleStyle(.switch).controlSize(.small).tint(Palette.accent)
                .disabled(!model.canChangeLargeAddressAware)
                .help("Allows a larger memory address space for Dragon Age: Origins only. This may help with memory-heavy play; it does not add physical RAM. Changes apply on the next launch.")
                Spacer(minLength: 12)
                Toggle(isOn: Binding(get: { model.selectedDeveloperConsole }, set: { model.chooseDeveloperConsole($0) })) {
                    Text("Developer console")
                        .font(.system(size: 12, weight: .semibold)).foregroundStyle(Palette.cream)
                }
                .toggleStyle(.switch).controlSize(.small).tint(Palette.accent)
                .disabled(!model.canChangeDeveloperConsole)
                .help("Applies when you press Play. The default console key is grave/backtick; its position varies by keyboard. Console text may be invisible. Launch options you set separately in Steam still apply.")
            }

        }
        .padding(18).frame(maxWidth: .infinity, alignment: .leading)
        .background(Palette.card).clipShape(RoundedRectangle(cornerRadius: 12))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Palette.line))
        .onAppear { model.loadDisplayOptions() }
    }
}

private struct LauncherView: View {
    @StateObject private var model = LauncherModel()

    private var statusCard: some View {
        VStack(alignment: .leading, spacing: 11) {
            HStack {
                Text(model.heading).font(.system(size: 17, weight: .semibold)).foregroundStyle(Palette.cream)
                Spacer()
                if (model.refreshing && model.status == nil) || model.busy || model.steamIsPreparing {
                    ProgressView().controlSize(.small).scaleEffect(0.8)
                        .accessibilityLabel(model.busy ? model.busyLabel : (model.steamIsPreparing ? model.heading : "Refreshing status"))
                }
            }
            Rectangle().fill(Palette.line).frame(height: 1)
            StatusRow(title: "Compatibility runtime", detail: model.status?.runtime_ready == true ? "Available" : "Not ready", ready: model.status?.runtime_ready == true)
            StatusRow(title: "Windows Steam", detail: model.steamDetail, ready: model.status?.steam_installed == true)
            StatusRow(title: model.status?.game_title ?? "Dragon Age: Origins", detail: model.status?.game_installed == true ? (model.status?.game_running == true ? "Running" : "Installed") : "Download through Steam", ready: model.status?.game_installed == true)
            if !model.platformReady || model.configurationRequired || model.status?.phase == "steam_installing" || model.status?.phase == "prefix_containment_required" {
                Text(model.status?.message ?? "")
                    .font(.system(size: 11)).foregroundStyle(Palette.muted).fixedSize(horizontal: false, vertical: true)
            }
            if model.steamMaintenanceActive {
                Text("Steam updates can take a few rounds. Startup continues automatically while this app is open, including when minimized.")
                    .font(.system(size: 11)).foregroundStyle(Palette.muted).fixedSize(horizontal: false, vertical: true)
            }
            if let message = model.status?.steam_maintenance_message, !message.isEmpty, model.steamMaintenanceMessage.isEmpty {
                Text(message).font(.system(size: 11)).foregroundStyle(Palette.muted)
                    .textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
            }
            if !model.steamMaintenanceMessage.isEmpty {
                Label(model.steamMaintenanceMessage, systemImage: model.steamMaintenanceIsError ? "exclamationmark.triangle" : "arrow.triangle.2.circlepath")
                    .font(.system(size: 11)).foregroundStyle(model.steamMaintenanceIsError ? Palette.accentText : Palette.muted)
                    .textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
            }
            if !model.statusFetchError.isEmpty {
                Label(model.statusFetchError, systemImage: "exclamationmark.triangle")
                    .font(.system(size: 11)).foregroundStyle(Palette.accentText).fixedSize(horizontal: false, vertical: true)
            }
        }.padding(18).frame(maxWidth: .infinity, alignment: .leading)
            .background(Palette.card).clipShape(RoundedRectangle(cornerRadius: 12))
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Palette.line))
    }

    private var setupAction: some View {
        Button { model.run("setup", label: "Setting up runtime & Steam…") } label: {
            Label(model.status?.phase == "steam_installing" ? "Steam setup is open" : "Set up & open Steam", systemImage: "arrow.down.circle")
        }.buttonStyle(PrimaryButton())
            .disabled(model.busy || model.status == nil || !model.platformReady || model.status?.phase == "steam_installing")
            .opacity(model.busy || model.status == nil || !model.platformReady || model.status?.phase == "steam_installing" ? 0.55 : 1)
    }

    private var launchActions: some View {
        HStack(spacing: 10) {
            if model.needsSetup || model.status == nil {
                setupAction
            } else if model.configurationRequired {
                Button { model.run("configure-game", label: "Opening first-time game setup…", arguments: model.gameArguments) } label: {
                    Label(model.status?.phase == "game_configuration_running" ? "Game setup is open" : "Finish game setup", systemImage: "slider.horizontal.3")
                }.buttonStyle(PrimaryButton()).disabled(model.busy || !model.platformReady || model.status?.phase == "game_configuration_running")
            } else if model.status?.game_installed == true {
                Button { model.run("play", label: "Starting game…", arguments: model.playArguments) } label: {
                    Label(model.status?.game_running == true ? "Game running" : "Play Dragon Age: Origins", systemImage: "play.fill")
                }.buttonStyle(PrimaryButton())
                    .disabled(model.busy || model.steamIsPreparing || model.status?.game_running == true || !model.canPlayWithDisplaySelection)
                    .opacity(model.busy || model.steamIsPreparing || model.status?.game_running == true || !model.canPlayWithDisplaySelection ? 0.55 : 1)
            } else if model.status?.steam_installed == true {
                Button { model.run("install-game", label: "Opening Steam download…", arguments: ["--appid", model.edition]) } label: {
                    Label(model.steamIsPreparing ? "Waiting for Steam…" : "Download in Steam", systemImage: "arrow.down.circle")
                }.buttonStyle(PrimaryButton()).disabled(model.busy || model.steamIsPreparing || !model.platformReady).opacity(model.busy || model.steamIsPreparing || !model.platformReady ? 0.55 : 1)
            } else {
                setupAction
            }
            Button { model.run("steam", label: "Opening Steam…") } label: { Label("Open Steam", systemImage: "arrow.up.forward.app") }
                .buttonStyle(QuietButton()).disabled(model.busy || model.steamIsPreparing || !model.platformReady || !model.prefixReady || model.status?.steam_installed != true)
                .opacity(model.busy || model.steamIsPreparing || !model.platformReady || !model.prefixReady || model.status?.steam_installed != true ? 0.45 : 1)
        }
    }

    private var setupPane: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Play your Steam copy on this Mac").font(.system(size: 18, weight: .semibold)).foregroundStyle(Palette.cream)
            Text("Origins Launcher is an unofficial Dragon Age: Origins launcher. Setup downloads a dedicated compatibility runtime (about 264 MB), then installs and opens Windows Steam. Steam updates and your game download are additional. A Steam copy of the game is required.")
                .font(.system(size: 12)).foregroundStyle(Palette.muted).fixedSize(horizontal: false, vertical: true)
            Text("Requires Apple Silicon, macOS 26 or later, and Rosetta. No Windows installation, Terminal, or separate developer tools are needed.")
                .font(.system(size: 11)).foregroundStyle(Palette.cream).fixedSize(horizontal: false, vertical: true)
            if model.status?.phase == "rosetta_required" {
                HStack(spacing: 12) {
                    if FileManager.default.fileExists(atPath: model.rosettaInstallerURL.path) {
                        Button("Open Rosetta installer") { model.openRosettaInstaller() }
                            .buttonStyle(QuietButton()).disabled(model.busy)
                    }
                    Link("Apple Rosetta help", destination: URL(string: "https://support.apple.com/102527")!)
                        .font(.system(size: 11)).foregroundStyle(Palette.accentText)
                }
                Text("Complete Apple’s installer prompts, then choose Refresh. Origins Launcher does not accept Apple’s agreement for you.")
                    .font(.system(size: 11)).foregroundStyle(Palette.muted).fixedSize(horizontal: false, vertical: true)
            }
            Divider().overlay(Palette.line)
            Text("Review the runtime and Steam terms before setup. The Sikarugir download includes Apple’s separately licensed D3DMetal component; this launcher leaves it disabled. Installers may present their own agreements for you to review.")
                .font(.system(size: 11)).foregroundStyle(Palette.muted).fixedSize(horizontal: false, vertical: true)
            HStack(spacing: 16) {
                Link("Sikarugir terms", destination: URL(string: "https://github.com/Sikarugir-App/Sikarugir#components-that-fall-under-lgpl-21-license")!)
                Link("Apple D3DMetal terms", destination: URL(string: "https://github.com/Sikarugir-App/Sikarugir/blob/main/D3DMetal/4.0/License.pdf")!)
                Link("Steam terms", destination: URL(string: "https://store.steampowered.com/subscriber_agreement/")!)
            }.font(.system(size: 11)).foregroundStyle(Palette.accentText)
            Text("The game and runtime stay in your Application Support folder. Optional DAFix UI scaling can be enabled after installing the game.")
                .font(.system(size: 11)).foregroundStyle(Palette.muted).fixedSize(horizontal: false, vertical: true)
        }.padding(18).frame(maxWidth: .infinity, alignment: .leading)
            .background(Palette.card).clipShape(RoundedRectangle(cornerRadius: 12))
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Palette.line))
    }

    var body: some View {
        VStack(spacing: 0) {
            // This geometry is only the scroll viewport; the action bar below
            // reserves its own height and stays visible at every window size.
            GeometryReader { geometry in
                ScrollView(.vertical) {
                VStack(alignment: .leading, spacing: 18) {
                    HStack(alignment: .center, spacing: 22) {
                        HStack(spacing: 12) {
                            if let logo = BrandAssets.logo {
                                Image(nsImage: logo).resizable().interpolation(.high).scaledToFit().frame(width: 84, height: 84)
                                    .accessibilityHidden(true)
                            }
                            VStack(alignment: .leading, spacing: 2) {
                                Text("ORIGINS").font(.system(size: 12, weight: .medium)).tracking(3.5).foregroundStyle(Palette.accentText)
                                Text("Launcher").font(.system(size: 34, weight: .regular, design: .serif)).foregroundStyle(Palette.cream)
                            }
                        }.fixedSize(horizontal: true, vertical: false)
                        statusCard
                    }

                    if model.needsSetup { setupPane }
                    if model.status?.steam_installed == true && model.status?.game_installed != true {
                        HStack(spacing: 12) {
                            Text("Your Steam edition").font(.system(size: 11)).foregroundStyle(Palette.muted)
                            Picker("Your Steam edition", selection: $model.edition) {
                                Text("Ultimate Edition").tag("47810")
                                Text("Original Edition").tag("17450")
                            }.pickerStyle(.segmented).labelsHidden().frame(maxWidth: 310).disabled(model.busy)
                            Spacer()
                        }
                    }
                    if model.displaySettingsReady { DisplaySettingsPanel(model: model) }
                    if model.configurationRequired {
                        Text("Choose Finish game setup, complete any supplied installers, then save your settings in the game’s configuration window and close it. Display controls appear once the configuration is ready.")
                            .font(.system(size: 12)).foregroundStyle(Palette.muted).fixedSize(horizontal: false, vertical: true)
                    } else if model.status?.steam_installed == true && model.status?.game_installed != true {
                        Text("Sign in to your own account in the Windows Steam window, then download your edition. Complete Steam Guard and any installer agreements there.")
                            .font(.system(size: 12)).foregroundStyle(Palette.muted).fixedSize(horizontal: false, vertical: true)
                    }

                    if model.busy {
                        Text(model.busyLabel).font(.system(size: 12, weight: .medium)).foregroundStyle(Palette.accentText)
                    }
                    if !model.notification.isEmpty {
                        HStack(alignment: .top, spacing: 7) {
                            Image(systemName: model.isError ? "exclamationmark.triangle" : "info.circle").padding(.top, 1)
                            Text(model.notification).textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
                            Spacer(minLength: 0)
                            if !model.busy { Button { model.notification = "" } label: { Image(systemName: "xmark") }.buttonStyle(.plain).help("Dismiss") }
                        }.font(.system(size: 11)).foregroundStyle(model.isError ? Palette.accentText : Palette.muted)
                    }

                    Spacer(minLength: 0)
                    Rectangle().fill(Palette.line).frame(height: 1)
                    HStack(spacing: 14) {
                        Button("Files") { if let path = model.status?.data_path { model.reveal(path) } }.disabled(model.status == nil)
                        Button("Logs") { if let path = model.status?.log_path { model.reveal(path) } }.disabled(model.status == nil)
                        Button("Diagnostics") { model.run("diagnostics", label: "Collecting diagnostics…") }.disabled(model.busy)
                        Button("Refresh") { model.refresh() }.disabled(model.busy || model.refreshing)
                        Spacer()
                        Button("Stop session") { model.showStopConfirmation = true }.disabled(model.busy || !model.hasSession)
                    }.buttonStyle(.plain).font(.system(size: 11)).foregroundStyle(Palette.muted)
                    Text(model.storage).help(model.storageHelp).font(.system(size: 10)).foregroundStyle(Palette.muted.opacity(0.8))
                }
                .padding(.horizontal, 30).padding(.top, 27).padding(.bottom, 22)
                .frame(minHeight: geometry.size.height, alignment: .top)
                }
            }
            VStack(spacing: 0) {
                Rectangle().fill(Palette.line).frame(height: 1)
                launchActions.padding(.horizontal, 30).padding(.vertical, 18)
            }.background(Palette.background)
        }
        .frame(minWidth: 740, minHeight: 520)
        .background(Palette.background).preferredColorScheme(.dark).tint(Palette.accent)
        .onAppear { model.refresh() }
        .alert("Stop this game session?", isPresented: $model.showStopConfirmation) {
            Button("Cancel", role: .cancel) {}
            Button("Stop session", role: .destructive) { model.run("stop", label: "Stopping this session…") }
        } message: {
            Text("This closes the game, Windows Steam, and compatibility processes in this launcher’s game environment. Save your progress first. Other Mac apps and other game environments are not targeted.")
        }
    }
}


private final class AppDelegate: NSObject, NSApplicationDelegate {
    private var terminationPending = false
    private var terminationReady = false

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        if terminationReady { return .terminateNow }
        if terminationPending { return .terminateLater }
        terminationPending = true
        let shutdown = LauncherLifetime.shared.beginShutdown()
        let maintenance = shutdown.maintenance
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            // Only this app's short-lived maintenance controller is cancelled.
            // Keep the native app alive until it exits, so it cannot reopen
            // Steam after the app has gone. Existing Steam/game processes stay.
            let deadline = Date().addingTimeInterval(3)
            while maintenance?.isRunning == true && Date() < deadline {
                Thread.sleep(forTimeInterval: 0.05)
            }
            if let maintenance, maintenance.isRunning {
                kill(maintenance.processIdentifier, SIGKILL)
                let killDeadline = Date().addingTimeInterval(2)
                while maintenance.isRunning && Date() < killDeadline { Thread.sleep(forTimeInterval: 0.05) }
            }
            // A fresh app uses a new owner even if an unrelated long operation
            // holds the backend lock and this bounded cleanup cannot acquire it.
            if shutdown.cancelStartup {
                _ = Controller.run(["steam-maintenance-cancel"], timeout: 5)
            }
            Task { @MainActor in
                self?.terminationReady = true
                NSApp.reply(toApplicationShouldTerminate: true)
            }
        }
        return .terminateLater
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

@main
struct OriginsLauncher: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    var body: some Scene {
        WindowGroup("Origins Launcher") { LauncherView() }
            .defaultSize(width: 800, height: 660)
            .windowStyle(.hiddenTitleBar)
            .commands {
                CommandGroup(replacing: .newItem) {}
                CommandGroup(replacing: .help) {
                    Button("About this launcher") {
                        let alert = NSAlert()
                        alert.messageText = "Origins Launcher"
                        alert.informativeText = "An unofficial Mac launcher for a Steam copy of Dragon Age: Origins that you own. BioWare, EA, Valve, Apple, and the compatibility-runtime maintainers are not affiliated with this project.\n\nLauncher code and documentation use GNU GPL version 3 only. See Licensing overview for source-sharing requirements and Artwork rights for separately licensed assets. The game, Steam, downloaded runtime and optional mods have separate licenses.\n\nClosing Origins Launcher cancels its automatic Steam startup follow-up and leaves the game and Steam running. Use Stop session to close this game environment."
                        alert.runModal()
                    }
                    Button("Project license") {
                        if let url = Bundle.main.url(forResource: "LICENSE", withExtension: nil) { NSWorkspace.shared.open(url) }
                    }
                    Button("Licensing overview") {
                        if let url = Bundle.main.url(forResource: "LICENSING", withExtension: "md") { NSWorkspace.shared.open(url) }
                    }
                    Button("Artwork rights") {
                        if let url = Bundle.main.url(forResource: "ARTWORK", withExtension: "md") { NSWorkspace.shared.open(url) }
                    }
                    Button("Third-party notices") {
                        if let url = Bundle.main.url(forResource: "THIRD_PARTY", withExtension: "md") { NSWorkspace.shared.open(url) }
                    }
                }
            }
    }
}
