import SwiftUI

struct SidebarView: View {
    @ObservedObject var viewModel: LibraryViewModel
    @Binding var showingSettings: Bool
    
    var body: some View {
        List(selection: $viewModel.selectedCollection) {
            Section(header: Text("Library")) {
                ForEach(viewModel.smartCollections) { collection in
                    NavigationLink(value: collection) {
                        Label(collection.name, systemImage: collection.icon ?? "folder")
                    }
                }
            }
        }
        .listStyle(SidebarListStyle())
        .navigationTitle("Arcade")
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                 Button(action: { showingSettings = true }) {
                     Image(systemName: "gear")
                 }
            }
        }
    }
}
