import React, {useState, useCallback, useEffect, useRef} from 'react';
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

	// Ref damit der Back-Handler immer den aktuellen panelIndex sieht
	// ohne bei jeder Änderung neu registriert zu werden
	const panelIndexRef = useRef(panelIndex);
	useEffect(() => {
		panelIndexRef.current = panelIndex;
	}, [panelIndex]);

	const handleSelectVideo = useCallback((video) => {
		setActiveVideo(video);
		setPanelIndex(1);
	}, []);

	const handleClosePlayer = useCallback(() => {
		setPanelIndex(0);
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

	// Back-Taste (webOS: 461, ESC: 27) global auf document abfangen
	// capture: true + stopImmediatePropagation verhindert dass VideoPlayer/Panels
	// das Event zuerst sehen und die "App beenden"-Frage triggern
	useEffect(() => {
		const handleBackKey = (ev) => {
			if (ev.keyCode !== 461 && ev.keyCode !== 27) return;

			const current = panelIndexRef.current;
			if (current === 1) {
				// Im VideoPlayer → zurück zum Grid, NICHT App beenden
				ev.preventDefault();
				ev.stopImmediatePropagation();
				setPanelIndex(0);
				setTimeout(() => setActiveVideo(null), 400);
			}
			// panelIndex 0 (Grid) oder 2 (Login) → Back-Taste normal durchlassen
		};

		document.addEventListener('keydown', handleBackKey, {capture: true});
		return () => document.removeEventListener('keydown', handleBackKey, {capture: true});
	}, []); // Leere Deps — einmalig registrieren, Ref liest immer aktuellen Wert

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
