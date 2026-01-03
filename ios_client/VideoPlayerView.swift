import SwiftUI
import AVKit

struct VideoPlayerView: View {
    let videoUrl: URL
    @State private var player: AVPlayer?
    
    var body: some View {
        VideoPlayer(player: player)
            .edgesIgnoringSafeArea(.all)
            .navigationBarTitleDisplayMode(.inline)
            .onAppear {
                if player == nil {
                    player = AVPlayer(url: videoUrl)
                    player?.play()
                }
            }
            .onDisappear {
                player?.pause()
                // Optional: set player to nil if you want to completely deallocate, 
                // but usually pause is enough. nil helps ensure no background audio.
                player = nil 
            }
    }
}
