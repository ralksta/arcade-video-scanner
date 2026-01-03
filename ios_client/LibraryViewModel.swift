import Foundation
import Combine

@MainActor
class LibraryViewModel: ObservableObject {
    @Published var videos: [Video] = []
    @Published var smartCollections: [SmartCollection] = []
    @Published var selectedCollection: SmartCollection? = .all {
        didSet {
            // When collection changes, reload library
            if oldValue?.id != selectedCollection?.id {
                Task { await refreshLibrary() }
            }
        }
    }
    
    @Published var isDarkMode: Bool {
        didSet {
            UserDefaults.standard.set(isDarkMode, forKey: "isDarkMode")
        }
    }
    
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var serverAddress: String {
        didSet {
            UserDefaults.standard.set(serverAddress, forKey: "serverAddress")
            Task { await loadCollections() } // Reload collections when server changes
        }
    }
    
    init() {
        self.serverAddress = UserDefaults.standard.string(forKey: "serverAddress") ?? "http://192.168.1.X:8000"
        self.isDarkMode = UserDefaults.standard.bool(forKey: "isDarkMode")
        Task { await loadCollections() }
    }
    
    func loadCollections() async {
         guard !serverAddress.contains("192.168.1.X") else { return }
         
         do {
             let collections = try await APIService.shared.fetchSmartCollections(serverUrl: serverAddress)
             // Prepend "All Videos"
             self.smartCollections = [.all] + collections
         } catch {
             print("Failed to load collections: \(error)")
             // Ensure at least "All" is present
             self.smartCollections = [.all]
         }
    }
    
    func refreshLibrary() async {
        guard !serverAddress.contains("192.168.1.X") else {
            self.errorMessage = "Please configure server address in settings."
            return
        }
        
        isLoading = true
        errorMessage = nil
        
        do {
            let fetchedVideos = try await APIService.shared.fetchLibrary(
                serverUrl: serverAddress,
                collectionId: selectedCollection?.id
            )
            self.videos = fetchedVideos
        } catch {
            self.errorMessage = "Failed to load library: \(error.localizedDescription)"
        }
        
        isLoading = false
    }
}
