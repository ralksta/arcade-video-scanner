import Foundation

struct Video: Identifiable, Codable {
    let id: String
    let title: String
    let videoUrl: String
    let thumbnailUrl: String?
    let duration: Int
    let is3d: Bool?
    let screenType: String?
    let stereoMode: String?
    
    // CodingKeys to map JSON keys to Swift properties
    enum CodingKeys: String, CodingKey {
        case title
        case videoUrl
        case thumbnailUrl
        case duration
        case is3d
        case screenType
        case stereoMode
    }
    
    // Custom init to create a unique ID since one isn't provided by the API directly
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        title = try container.decode(String.self, forKey: .title)
        videoUrl = try container.decode(String.self, forKey: .videoUrl)
        thumbnailUrl = try container.decodeIfPresent(String.self, forKey: .thumbnailUrl)
        duration = try container.decode(Int.self, forKey: .duration)
        is3d = try container.decodeIfPresent(Bool.self, forKey: .is3d)
        screenType = try container.decodeIfPresent(String.self, forKey: .screenType)
        stereoMode = try container.decodeIfPresent(String.self, forKey: .stereoMode)
        
        // Generate ID from url to ensure uniqueness
        id = videoUrl
    }
}

struct DeoVRResponse: Codable {
    let scenes: [Video]
}
