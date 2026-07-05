import React, {useState, useCallback, useEffect} from 'react';
import ThemeDecorator from '@enact/limestone/ThemeDecorator';
import Panels, {Panel} from '@enact/limestone/Panels';
import VideoPlayer, {Video} from '@enact/limestone/VideoPlayer';

import MainPanel from '../views/MainPanel';
import LoginPanel from '../views/LoginPanel';
import css from './App.module.less';

const App = (props) => {
	const existingToken = typeof window !== 'undefined' ? localStorage.getItem('arcade_session_token') : null;

	// Starte direkt auf LoginPanel (index 2) wenn kein Token vorhanden
	const [panelIndex, setPanelIndex] = useState(existingToken ? 0 : 2);
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

	// webOS Back-Taste (461) abfangen — verhindert App-Beenden beim VideoPlayer
	useEffect(() => {
		const handleBackKey = (ev) => {
			// keyCode 461 = webOS Fernbedienung Back, 27 = ESC (Entwicklung)
			if (ev.keyCode === 461 || ev.keyCode === 27) {
				if (panelIndex === 1) {
					// Im VideoPlayer → zurück zum Grid
					ev.preventDefault();
					ev.stopPropagation();
					setPanelIndex(0);
					setTimeout(() => setActiveVideo(null), 400);
				}
				// Bei panelIndex 0 oder 2 → normales Back (App beenden) erlaubt
			}
		};
		window.addEventListener('keydown', handleBackKey, true);
		return () => window.removeEventListener('keydown', handleBackKey, true);
	}, [panelIndex]);

	const sessionToken = typeof window !== 'undefined' ? localStorage.getItem('arcade_session_token') : '';

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
								<source src={`http://192.168.2.183:8000/stream?path=${encodeURIComponent(activeVideo.FilePath)}&token=${encodeURIComponent(sessionToken || '')}`} />
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
