import SwiftUI

struct VideoGridView: View {
    @ObservedObject var viewModel: LibraryViewModel
    var showHeader: Bool = true
    
    let columns = [
        GridItem(.adaptive(minimum: 160), spacing: 16)
    ]
    
    var body: some View {
        ScrollView {
            VStack(spacing: 0) {
                // Header Image - only show on All Videos
                if showHeader {
                    Image("arcade_header")
                        .resizable()
                        .aspectRatio(contentMode: .fit)
                        .frame(maxWidth: .infinity)
                        .padding(.bottom, 16)
                }
                
                // Video Grid
                LazyVGrid(columns: columns, spacing: 16) {
                ForEach(viewModel.videos) { video in
                    NavigationLink(destination: VideoPlayerView(videoUrl: URL(string: video.videoUrl)!)) {
                        VStack(alignment: .leading) {
                            if let thumbUrl = video.thumbnailUrl, let url = URL(string: thumbUrl) {
                                AsyncImage(url: url) { phase in
                                    switch phase {
                                    case .empty:
                                        Rectangle()
                                            .fill(Color.gray.opacity(0.3))
                                            .aspectRatio(16/9, contentMode: .fit)
                                            .overlay(ProgressView())
                                    case .success(let image):
                                        image
                                            .resizable()
                                            .aspectRatio(16/9, contentMode: .fit)
                                    case .failure:
                                        Rectangle()
                                            .fill(Color.gray.opacity(0.3))
                                            .aspectRatio(16/9, contentMode: .fit)
                                            .overlay(Image(systemName: "film"))
                                    @unknown default:
                                        EmptyView()
                                    }
                                }
                                .cornerRadius(8)
                            } else {
                                Rectangle()
                                    .fill(Color.gray.opacity(0.3))
                                    .aspectRatio(16/9, contentMode: .fit)
                                    .overlay(Image(systemName: "film"))
                                    .cornerRadius(8)
                            }
                            
                            Text(video.title)
                                .font(.caption)
                                .fontWeight(.medium)
                                .lineLimit(2)
                                .multilineTextAlignment(.leading)
                            
                            Text(formatDuration(seconds: video.duration))
                                .font(.caption2)
                                .foregroundColor(.secondary)
                        }
                    }
                    .buttonStyle(PlainButtonStyle())
                }
            }
            .padding(.horizontal)
            } // End VStack
        }
    }
    
    private func formatDuration(seconds: Int) -> String {
        let h = seconds / 3600
        let m = (seconds % 3600) / 60
        let s = seconds % 60
        if h > 0 {
            return String(format: "%d:%02d:%02d", h, m, s)
        } else {
            return String(format: "%d:%02d", m, s)
        }
    }
}
