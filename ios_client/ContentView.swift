import SwiftUI

struct ContentView: View {
    @StateObject private var viewModel = LibraryViewModel()
    @State private var showingSettings = false
    @State private var columnVisibility: NavigationSplitViewVisibility = .doubleColumn
    
    var body: some View {
        if #available(iOS 16.0, *) {
             NavigationSplitView(columnVisibility: $columnVisibility) {
                 SidebarView(viewModel: viewModel, showingSettings: $showingSettings)
             } detail: {
                 NavigationStack {
                     VideoGridContainer(viewModel: viewModel)
                 }
             }
             .sheet(isPresented: $showingSettings) {
                 SettingsView(viewModel: viewModel)
             }
             .onAppear {
                 Task {
                      await viewModel.loadCollections()
                      await viewModel.refreshLibrary()
                 }
             }
             .preferredColorScheme(viewModel.isDarkMode ? .dark : .light)
        } else {
            // Fallback for older iOS (NavigationView)
            NavigationView {
                SidebarView(viewModel: viewModel, showingSettings: $showingSettings)
                VideoGridContainer(viewModel: viewModel)
            }
            .sheet(isPresented: $showingSettings) {
                SettingsView(viewModel: viewModel)
            }
            .preferredColorScheme(viewModel.isDarkMode ? .dark : .light)
        }
    }
}

// Extracted to keep cleaner
struct VideoGridContainer: View {
    @ObservedObject var viewModel: LibraryViewModel
    
    var body: some View {
        ZStack {
            if viewModel.isLoading {
                ProgressView("Loading videos...")
            } else if let error = viewModel.errorMessage {
                VStack(spacing: 16) {
                    Image(systemName: "wifi.exclamationmark")
                        .font(.largeTitle)
                        .foregroundColor(.orange)
                    Text(error)
                        .multilineTextAlignment(.center)
                        .padding()
                    Button("Retry") {
                        Task { await viewModel.refreshLibrary() }
                    }
                    .buttonStyle(.bordered)
                }
            } else if viewModel.videos.isEmpty {
                 VStack {
                    Text("No videos in this collection.")
                        .foregroundColor(.secondary)
                    Button("Refresh") {
                        Task { await viewModel.refreshLibrary() }
                    }
                    .padding()
                }
            } else {
                VideoGridView(
                    viewModel: viewModel,
                    showHeader: viewModel.selectedCollection?.id == "all"
                )
            }
        }
        .navigationTitle(navigationTitleWithCount)
    }
    
    private var navigationTitleWithCount: String {
        let name = viewModel.selectedCollection?.name ?? "Videos"
        let count = viewModel.videos.count
        if count > 0 {
            return "\(name) (\(count) Videos)"
        }
        return name
    }
}
