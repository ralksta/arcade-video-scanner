import React, {useState, useCallback} from 'react';
import ThemeDecorator from '@enact/limestone/ThemeDecorator';
import Panels, {Panel} from '@enact/limestone/Panels';
import VideoPlayer, {Video} from '@enact/limestone/VideoPlayer';

import MainPanel from '../views/MainPanel';
import LoginPanel from '../views/LoginPanel';
import css from './App.module.less';

const App = (props) => {
	const [panelIndex, setPanelIndex] = useState(0);
	const [activeVideo, setActiveVideo] = useState(null);

	const handleSelectVideo = useCallback((video) => {
		setActiveVideo(video);
		setPanelIndex(1);
	}, []);

	const handleClosePlayer = useCallback(() => {
		setPanelIndex(0);
		// Gib der Panel-Animation etwas Zeit, bevor wir das Video entladen
		setTimeout(() => {
			setActiveVideo(null);
		}, 400);
	}, []);

	const handleAuthFailed = useCallback(() => {
		setPanelIndex(2);
	}, []);

	const handleLoginSuccess = useCallback(() => {
		setPanelIndex(0);
	}, []);

	return (
		<div {...props} className={css.app}>
			<Panels index={panelIndex} noCloseButton>
				<MainPanel onSelectVideo={handleSelectVideo} onAuthFailed={handleAuthFailed} />
				<Panel>
					{activeVideo && (
						<VideoPlayer 
							title={activeVideo._fileName} 
							onBack={handleClosePlayer}
							autoCloseTimeout={3000}
						>
							<Video>
								<source src={`http://192.168.2.183:8000/stream?path=${encodeURIComponent(activeVideo.FilePath)}`} />
							</Video>
						</VideoPlayer>
					)}
				</Panel>
				<LoginPanel onLoginSuccess={handleLoginSuccess} />
			</Panels>
		</div>
	);
};

export default ThemeDecorator(App);
