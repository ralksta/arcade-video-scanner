import React, {useState, useCallback, useEffect, useRef} from 'react';
import {serverUrl} from '../serverConfig';
import {getItem} from '../safeStorage';
import displayName from '../displayName';
import {getProgress, saveProgress} from '../watchProgress';
import ThemeDecorator from '@enact/limestone/ThemeDecorator';
import Panels, {Panel} from '@enact/limestone/Panels';
import VideoPlayer, {Video} from '@enact/limestone/VideoPlayer';

import MainPanel from '../views/MainPanel';
import LoginPanel from '../views/LoginPanel';
import css from './App.module.less';

const App = (props) => {
	const existingToken = getItem('arcade_session_token');

	// Starte direkt auf LoginPanel (index 2) wenn kein Token vorhanden
	const [panelIndex, setPanelIndex] = useState(existingToken ? 0 : 2);
	const [activeVideo, setActiveVideo] = useState(null);

	// Ref damit der Back-Handler immer den aktuellen panelIndex sieht
	// ohne bei jeder Änderung neu registriert zu werden
	const panelIndexRef = useRef(panelIndex);
	// Der Back-Handler wird einmal registriert; über die Ref sieht er immer
	// die aktuelle Sicherungsfunktion.
	const saveRef = useRef(() => {});
	useEffect(() => {
		panelIndexRef.current = panelIndex;
	}, [panelIndex]);

	// Wiedergabe: Position merken und dort fortsetzen („Weiterschauen“).
	const playerRef = useRef(null);
	const lastSavedRef = useRef(0);
	// Zielposition fürs Fortsetzen; wird beim ersten timeupdate angewendet.
	const pendingResumeRef = useRef(0);
	// Zählt hoch, wenn sich gespeicherte Positionen geändert haben könnten —
	// MainPanel liest „Weiterschauen“ dann neu ein.
	const [progressVersion, setProgressVersion] = useState(0);

	const handleSelectVideo = useCallback((video, options = {}) => {
		lastSavedRef.current = 0;
		pendingResumeRef.current = options.fromStart ? 0 : getProgress(video.FilePath);
		setActiveVideo(video);
		setPanelIndex(1);
	}, []);

	const savePosition = useCallback(() => {
		const player = playerRef.current;
		if (!player || !activeVideo) return;
		const {currentTime, duration} = player.getMediaState();
		saveProgress(activeVideo.FilePath, currentTime, duration);
	}, [activeVideo]);
	useEffect(() => {
		saveRef.current = savePosition;
	}, [savePosition]);

	// Alle fünf Sekunden sichern — ein abgestürzter Player soll nicht alles
	// verlieren.
	//
	// Das Fortsetzen passiert ebenfalls hier, beim ersten timeupdate: In
	// onLoadedMetadata hält Limestone die Quelle noch für „nicht verfügbar“
	// und verwirft seek() still — gemessen startete das Video bei 0.
	const handleTimeUpdate = useCallback(() => {
		if (pendingResumeRef.current > 0 && playerRef.current) {
			const resumeAt = pendingResumeRef.current;
			pendingResumeRef.current = 0;
			playerRef.current.seek(resumeAt);
			return;
		}
		const now = Date.now();
		if (now - lastSavedRef.current < 5000) return;
		lastSavedRef.current = now;
		savePosition();
	}, [savePosition]);

	const handleClosePlayer = useCallback(() => {
		savePosition();
		setProgressVersion(v => v + 1);
		setPanelIndex(0);
		setTimeout(() => {
			setActiveVideo(null);
		}, 400);
	}, [savePosition]);

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
				saveRef.current();
				setProgressVersion(v => v + 1);
				setPanelIndex(0);
				setTimeout(() => setActiveVideo(null), 400);
			}
			// panelIndex 0 (Grid) oder 2 (Login) → Back-Taste normal durchlassen
		};

		document.addEventListener('keydown', handleBackKey, {capture: true});
		return () => document.removeEventListener('keydown', handleBackKey, {capture: true});
	}, []); // Leere Deps — einmalig registrieren, Ref liest immer aktuellen Wert

	const sessionToken = getItem('arcade_session_token', '');

	return (
		<div {...props} className={css.app}>
			<Panels index={panelIndex} noCloseButton>
				<MainPanel onSelectVideo={handleSelectVideo} onAuthFailed={handleAuthFailed} progressVersion={progressVersion} />
				<Panel>
					{activeVideo && (
						<VideoPlayer
							ref={playerRef}
							title={displayName(activeVideo)}
							onBack={handleClosePlayer}
							onTimeUpdate={handleTimeUpdate}
							autoCloseTimeout={3000}
						>
							<Video>
								<source src={serverUrl(`/stream?path=${encodeURIComponent(activeVideo.FilePath)}&token=${encodeURIComponent(sessionToken || '')}`)} />
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
