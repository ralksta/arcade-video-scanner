import SwiftUI

struct SettingsView: View {
    @ObservedObject var viewModel: LibraryViewModel
    @Environment(\.presentationMode) var presentationMode
    
    var body: some View {
        NavigationView {
            Form {
                Section(header: Text("Server Configuration")) {
                    TextField("Server URL (e.g. http://192.168.1.5:8000)", text: $viewModel.serverAddress)
                        .autocapitalization(.none)
                        .disableAutocorrection(true)
                        .keyboardType(.URL)
                }
                
                Section(header: Text("Appearance")) {
                    Toggle("Dark Mode", isOn: $viewModel.isDarkMode)
                }
                
                Section(footer: Text("Enter the full URL of your Arcade Media Scanner server.")) {
                    Button("Save") {
                        Task {
                            await viewModel.refreshLibrary()
                            presentationMode.wrappedValue.dismiss()
                        }
                    }
                }
            }
            .navigationTitle("Settings")
            .navigationBarItems(trailing: Button("Done") {
                presentationMode.wrappedValue.dismiss()
            })
        }
    }
}
