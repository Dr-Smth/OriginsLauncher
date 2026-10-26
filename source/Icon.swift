import AppKit
import Foundation

// Default foreground: original vector artwork, drawn entirely in code.
// An optional external image replaces only the foreground in a local build.
func color(_ hex: UInt32, _ alpha: CGFloat = 1) -> NSColor {
    NSColor(calibratedRed: CGFloat((hex >> 16) & 255) / 255,
            green: CGFloat((hex >> 8) & 255) / 255,
            blue: CGFloat(hex & 255) / 255, alpha: alpha)
}
func gradient(_ path: NSBezierPath, _ bottom: NSColor, _ top: NSColor) {
    NSGradient(starting: bottom, ending: top)!.draw(in: path, angle: 90)
}
func polygon(_ points: [NSPoint]) -> NSBezierPath {
    let path = NSBezierPath()
    path.move(to: points[0])
    for point in points.dropFirst() { path.line(to: point) }
    path.close()
    return path
}
func shield(_ inset: CGFloat = 0) -> NSBezierPath {
    let path = NSBezierPath()
    path.move(to: NSPoint(x: 512, y: 854))
    path.curve(to: NSPoint(x: 782, y: 782), controlPoint1: NSPoint(x: 610, y: 827), controlPoint2: NSPoint(x: 718, y: 798))
    path.curve(to: NSPoint(x: 758, y: 466), controlPoint1: NSPoint(x: 793, y: 655), controlPoint2: NSPoint(x: 793, y: 558))
    path.curve(to: NSPoint(x: 512, y: 181), controlPoint1: NSPoint(x: 720, y: 354), controlPoint2: NSPoint(x: 627, y: 251))
    path.curve(to: NSPoint(x: 266, y: 466), controlPoint1: NSPoint(x: 397, y: 251), controlPoint2: NSPoint(x: 304, y: 354))
    path.curve(to: NSPoint(x: 242, y: 782), controlPoint1: NSPoint(x: 231, y: 558), controlPoint2: NSPoint(x: 231, y: 655))
    path.curve(to: NSPoint(x: 512, y: 854), controlPoint1: NSPoint(x: 306, y: 798), controlPoint2: NSPoint(x: 414, y: 827))
    path.close()
    if inset > 0 {
        let transform = AffineTransform(translationByX: 512, byY: 520)
        var final = transform
        final.scale(1 - inset)
        final.translate(x: -512, y: -520)
        path.transform(using: final)
    }
    return path
}
func paint(artwork: NSImage?) {
    let outer = NSBezierPath(roundedRect: NSRect(x: 60, y: 60, width: 904, height: 904), xRadius: 204, yRadius: 204)
    NSGraphicsContext.saveGraphicsState()
    let shadow = NSShadow()
    shadow.shadowColor = color(0x000000, 0.42)
    shadow.shadowBlurRadius = 24
    shadow.shadowOffset = NSSize(width: 0, height: -11)
    shadow.set()
    gradient(outer, color(0x13151A), color(0x29292D))
    NSGraphicsContext.restoreGraphicsState()
    outer.lineWidth = 3
    color(0xF5D995, 0.16).setStroke()
    outer.stroke()
    let inset = NSBezierPath(roundedRect: NSRect(x: 80, y: 80, width: 864, height: 864), xRadius: 185, yRadius: 185)
    inset.lineWidth = 1.5
    color(0xE7C890, 0.09).setStroke()
    inset.stroke()

    if let artwork = artwork {
        // Preserve the supplied image and its transparent padding/aspect ratio.
        // The tile, border and shadow above are identical to the fallback icon.
        let available = NSRect(x: 72, y: 72, width: 880, height: 880)
        let scale = min(available.width / artwork.size.width,
                        available.height / artwork.size.height)
        let size = NSSize(width: artwork.size.width * scale, height: artwork.size.height * scale)
        let destination = NSRect(x: available.midX - size.width / 2,
                                 y: available.midY - size.height / 2,
                                 width: size.width, height: size.height)
        NSGraphicsContext.current?.imageInterpolation = .high
        artwork.draw(in: destination, from: .zero, operation: .sourceOver, fraction: 1)
        return
    }

    NSGraphicsContext.saveGraphicsState()
    let shieldShadow = NSShadow()
    shieldShadow.shadowColor = color(0x000000, 0.65)
    shieldShadow.shadowBlurRadius = 30
    shieldShadow.shadowOffset = NSSize(width: 0, height: -15)
    shieldShadow.set()
    gradient(shield(), color(0x8A572C), color(0xF8DEA4))
    NSGraphicsContext.restoreGraphicsState()
    gradient(shield(0.045), color(0x251319), color(0x721E2D))
    let inner = shield(0.078)
    inner.lineWidth = 2
    color(0xE4B96D, 0.35).setStroke()
    inner.stroke()

    // Broad angular wings remain legible at small Dock/Finder sizes.
    let leftWing = polygon([NSPoint(x: 496, y: 566), NSPoint(x: 338, y: 701),
        NSPoint(x: 361, y: 590), NSPoint(x: 322, y: 607), NSPoint(x: 386, y: 509),
        NSPoint(x: 434, y: 481)])
    gradient(leftWing, color(0xB97A39), color(0xE4B86E))
    let rightWing = polygon([NSPoint(x: 582, y: 566), NSPoint(x: 697, y: 674),
        NSPoint(x: 676, y: 571), NSPoint(x: 710, y: 589), NSPoint(x: 650, y: 481),
        NSPoint(x: 600, y: 461)])
    gradient(rightWing, color(0x8E552D), color(0xD3A15C))

    let dragon = NSBezierPath()
    dragon.move(to: NSPoint(x: 563, y: 694))
    dragon.curve(to: NSPoint(x: 609, y: 614), controlPoint1: NSPoint(x: 626, y: 692), controlPoint2: NSPoint(x: 640, y: 648))
    dragon.curve(to: NSPoint(x: 491, y: 507), controlPoint1: NSPoint(x: 594, y: 566), controlPoint2: NSPoint(x: 501, y: 567))
    dragon.curve(to: NSPoint(x: 487, y: 427), controlPoint1: NSPoint(x: 451, y: 483), controlPoint2: NSPoint(x: 451, y: 450))
    dragon.curve(to: NSPoint(x: 600, y: 329), controlPoint1: NSPoint(x: 553, y: 415), controlPoint2: NSPoint(x: 613, y: 384))
    dragon.curve(to: NSPoint(x: 511, y: 363), controlPoint1: NSPoint(x: 577, y: 331), controlPoint2: NSPoint(x: 547, y: 346))
    dragon.curve(to: NSPoint(x: 398, y: 473), controlPoint1: NSPoint(x: 389, y: 369), controlPoint2: NSPoint(x: 373, y: 438))
    dragon.curve(to: NSPoint(x: 520, y: 599), controlPoint1: NSPoint(x: 420, y: 528), controlPoint2: NSPoint(x: 527, y: 553))
    dragon.curve(to: NSPoint(x: 537, y: 649), controlPoint1: NSPoint(x: 544, y: 619), controlPoint2: NSPoint(x: 545, y: 637))
    dragon.line(to: NSPoint(x: 514, y: 678))
    dragon.line(to: NSPoint(x: 543, y: 678))
    dragon.close()
    gradient(dragon, color(0xD49C55), color(0xFFE9B9))

    let head = polygon([NSPoint(x: 542, y: 673), NSPoint(x: 535, y: 733),
        NSPoint(x: 568, y: 711), NSPoint(x: 609, y: 769), NSPoint(x: 609, y: 711),
        NSPoint(x: 671, y: 679), NSPoint(x: 657, y: 646), NSPoint(x: 607, y: 653),
        NSPoint(x: 575, y: 633)])
    gradient(head, color(0xDFB978), color(0xFFF0C8))
    color(0x4A1721).setFill()
    polygon([NSPoint(x: 612, y: 688), NSPoint(x: 637, y: 676), NSPoint(x: 614, y: 673)]).fill()
    let eye = NSBezierPath(ovalIn: NSRect(x: 615, y: 675, width: 6, height: 6))
    color(0xFF743E).setFill()
    eye.fill()

    let jewel = polygon([NSPoint(x: 512, y: 304), NSPoint(x: 527, y: 283),
        NSPoint(x: 512, y: 262), NSPoint(x: 497, y: 283)])
    gradient(jewel, color(0x8E1F2D), color(0xE04A4D))
    jewel.lineWidth = 1.5
    color(0xEDBD72, 0.8).setStroke()
    jewel.stroke()
}

let arguments = CommandLine.arguments
if arguments.count != 2 && arguments.count != 3 {
    fputs("Usage: IconGenerator output-directory [external-artwork-image]\n", stderr)
    exit(2)
}
var artwork: NSImage?
if arguments.count == 3 {
    guard let loaded = NSImage(contentsOfFile: arguments[2]),
          loaded.isValid, loaded.size.width > 0, loaded.size.height > 0 else {
        fputs("Cannot read the external artwork image.\n", stderr)
        exit(2)
    }
    artwork = loaded
}
let output = URL(fileURLWithPath: arguments[1], isDirectory: true)
let iconset = output.appendingPathComponent("DragonAgeOrigins.iconset", isDirectory: true)
try FileManager.default.createDirectory(at: iconset, withIntermediateDirectories: true)
let variants: [(String, Int)] = [
    ("icon_16x16.png", 16), ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32), ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128), ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256), ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512), ("icon_512x512@2x.png", 1024)]
for (name, size) in variants {
    let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: size,
        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
        colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
    let context = NSGraphicsContext(bitmapImageRep: bitmap)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    context.cgContext.scaleBy(x: CGFloat(size) / 1024, y: CGFloat(size) / 1024)
    context.cgContext.setAllowsAntialiasing(true)
    context.cgContext.setShouldAntialias(true)
    paint(artwork: artwork)
    NSGraphicsContext.restoreGraphicsState()
    let png = bitmap.representation(using: .png, properties: [:])!
    try png.write(to: iconset.appendingPathComponent(name))
    if size == 1024 { try png.write(to: output.appendingPathComponent("icon-preview.png")) }
}
print(iconset.path)
