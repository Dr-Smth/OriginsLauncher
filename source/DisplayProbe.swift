import AppKit
import CoreGraphics
import Foundation
import Darwin

// Read-only display inventory. No windows, mode switches, preferences, device
// serial numbers, or game/runtime actions are involved.
struct DisplayInfo: Encodable {
    let id: String
    let name: String
    let is_main: Bool
    let builtin: Bool
    let logical_width: Int
    let logical_height: Int
    let pixel_width: Int
    let pixel_height: Int
    let scale: Double
    let refresh_rate: Double
    let available_pixel_width: Int
    let available_pixel_height: Int
}
struct DisplayInventory: Encodable {
    let schema_version = 1
    let displays: [DisplayInfo]
    let main_display_id: String
}
func fail(_ message: String) -> Never {
    let result: [String: Any] = ["schema_version": 1, "displays": [], "main_display_id": NSNull(), "error": message]
    let data = (try? JSONSerialization.data(withJSONObject: result, options: [.sortedKeys])) ?? Data("{}".utf8)
    FileHandle.standardOutput.write(data + Data([10]))
    exit(1)
}

let mainID = CGMainDisplayID()
let screens = NSScreen.screens
if screens.isEmpty { fail("No active display is available to the launcher.") }
var displays: [DisplayInfo] = []
for screen in screens {
    guard let number = screen.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? NSNumber else {
        fail("An active display did not provide its display identifier.")
    }
    let displayID = CGDirectDisplayID(number.uint32Value)
    guard let mode = CGDisplayCopyDisplayMode(displayID) else {
        fail("The active display mode could not be read. Reconnect the display and try again.")
    }
    let frame = screen.frame
    let available = screen.visibleFrame
    let scale = screen.backingScaleFactor
    let refresh = mode.refreshRate
    guard scale.isFinite, scale > 0, frame.width > 0, frame.height > 0,
          mode.pixelWidth > 0, mode.pixelHeight > 0, available.width > 0, available.height > 0 else {
        fail("The active display returned invalid dimensions.")
    }
    displays.append(DisplayInfo(
        id: String(displayID), name: screen.localizedName,
        is_main: displayID == mainID, builtin: CGDisplayIsBuiltin(displayID) != 0,
        logical_width: Int(frame.width.rounded()), logical_height: Int(frame.height.rounded()),
        pixel_width: mode.pixelWidth, pixel_height: mode.pixelHeight,
        scale: Double(scale), refresh_rate: refresh.isFinite && refresh > 0 ? refresh : 0,
        // The backend subtracts the window-title-bar margin from these bounds.
        available_pixel_width: min(mode.pixelWidth, Int(floor(available.width * scale))),
        available_pixel_height: min(mode.pixelHeight, Int(floor(available.height * scale)))
    ))
}
if !displays.contains(where: { $0.is_main }) { fail("The main active display could not be identified.") }
displays.sort { left, right in
    if left.is_main != right.is_main { return left.is_main }
    return left.id < right.id
}
do {
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.sortedKeys]
    let output = try encoder.encode(DisplayInventory(displays: displays, main_display_id: String(mainID)))
    FileHandle.standardOutput.write(output + Data([10]))
} catch {
    fail("Display information could not be encoded.")
}
