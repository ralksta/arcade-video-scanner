import Foundation

struct SmartCollection: Identifiable, Codable, Hashable {
    let id: String
    let name: String
    let icon: String?
    // We don't need criteria here for the client
    
    // Default "All Videos" collection helper
    static let all = SmartCollection(id: "all", name: "All Videos", icon: "square.grid.2x2")
}

struct SettingsResponse: Codable {
    let smart_collections: [SmartCollection]
}
