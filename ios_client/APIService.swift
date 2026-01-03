import Foundation

enum APIError: Error {
    case invalidURL
    case networkError(Error)
    case decodingError(Error)
}

class APIService {
    static let shared = APIService()
    
    private init() {}
    
    func fetchLibrary(serverUrl: String, collectionId: String? = nil) async throws -> [Video] {
        // Ensure URL doesn't end with slash to avoid double slashes if user inputs one
        let cleanUrl = serverUrl.trimmingCharacters(in: .init(charactersIn: "/"))
        
        let endpoint: String
        if let id = collectionId, id != "all" {
             endpoint = "\(cleanUrl)/api/deovr/collection/\(id).json"
        } else {
             endpoint = "\(cleanUrl)/api/deovr/library.json"
        }
        
        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }
        
        let (data, _) = try await URLSession.shared.data(from: url)
        
        // Handle case where collection endpoint returns a dict with "scenes" vs potential other formats
        // The generator currently returns the same structure { "scenes": [...] }
        
        let decoder = JSONDecoder()
        let response = try decoder.decode(DeoVRResponse.self, from: data)
        
        return response.scenes
    }
    
    func fetchSmartCollections(serverUrl: String) async throws -> [SmartCollection] {
        let cleanUrl = serverUrl.trimmingCharacters(in: .init(charactersIn: "/"))
        let endpoint = "\(cleanUrl)/api/settings"
        
        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }
        
        let (data, _) = try await URLSession.shared.data(from: url)
        
        let decoder = JSONDecoder()
        let response = try decoder.decode(SettingsResponse.self, from: data)
        
        return response.smart_collections
    }
}
