import React, {useState, useCallback, useEffect} from 'react';
import PropTypes from 'prop-types';
import {Panel, Header} from '@enact/limestone/Panels';
import {InputField} from '@enact/limestone/Input';
import Button from '@enact/limestone/Button';
import Heading from '@enact/limestone/Heading';
import BodyText from '@enact/limestone/BodyText';

import credentials from './credentials.json';

const LoginPanel = ({onLoginSuccess, ...props}) => {
	const [username, setUsername] = useState('');
	const [password, setPassword] = useState('');
	const [error, setError] = useState('');
	const [loading, setLoading] = useState(false);

	const handleUsernameChange = useCallback((ev) => {
		setUsername(ev.value);
	}, []);

	const handlePasswordChange = useCallback((ev) => {
		setPassword(ev.value);
	}, []);

	const handleLogin = useCallback(() => {
		if (!username || !password) {
			setError('Bitte Benutzernamen und Passwort eingeben.');
			return;
		}

		setLoading(true);
		setError('');

		fetch('http://192.168.2.183:8000/api/login', {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				'X-Enact-TV': 'true'
			},
			body: JSON.stringify({
				username,
				password,
				remember: true
			})
		})
			.then(res => {
				if (!res.ok) {
					if (res.status === 401) {
						throw new Error('Falsche Zugangsdaten.');
					}
					throw new Error('Serverfehler.');
				}
				return res.json();
			})
			.then(data => {
				if (data.success && data.token) {
					localStorage.setItem('arcade_session_token', data.token);
					onLoginSuccess(data.token);
				} else {
					throw new Error('Login fehlgeschlagen.');
				}
			})
			.catch(err => {
				setError(err.message || 'Verbindungsfehler.');
				setLoading(false);
			});
	}, [username, password, onLoginSuccess]);

	// Automatischer Login bei geladenen credentials.json
	useEffect(() => {
		if (credentials && credentials.username && credentials.password && !loading && !error) {
			setLoading(true);
			fetch('http://192.168.2.183:8000/api/login', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'X-Enact-TV': 'true'
				},
				body: JSON.stringify({
					username: credentials.username,
					password: credentials.password,
					remember: true
				})
			})
				.then(res => {
					if (!res.ok) throw new Error('Automatischer Login fehlgeschlagen.');
					return res.json();
				})
				.then(data => {
					if (data.success && data.token) {
						localStorage.setItem('arcade_session_token', data.token);
						onLoginSuccess(data.token);
					} else {
						throw new Error('Automatischer Login fehlgeschlagen.');
					}
				})
				.catch(err => {
					console.warn('Auto-login failed, falling back to manual login:', err);
					setError('Automatischer Login fehlgeschlagen. Bitte manuell anmelden.');
					setLoading(false);
				});
		}
	}, [onLoginSuccess]);

	return (
		<Panel {...props}>
			<Header title="Login" subtitle="Bitte melde dich an, um auf die Mediathek zuzugreifen." />
			<div style={{maxWidth: '600px', margin: '40px auto', display: 'flex', flexDirection: 'column', gap: '20px'}}>
				<div>
					<Heading size="small">Benutzername</Heading>
					<InputField 
						placeholder="Benutzername eingeben" 
						value={username}
						onChange={handleUsernameChange}
						disabled={loading}
					/>
				</div>
				<div>
					<Heading size="small">Passwort</Heading>
					<InputField 
						placeholder="Passwort eingeben" 
						type="password"
						value={password}
						onChange={handlePasswordChange}
						disabled={loading}
					/>
				</div>
				{error && (
					<BodyText style={{color: '#ff4d4d', margin: '10px 0'}}>
						{error}
					</BodyText>
				)}
				<Button 
					onClick={handleLogin}
					disabled={loading}
					style={{marginTop: '20px'}}
				>
					{loading ? 'Anmelden...' : 'Anmelden'}
				</Button>
			</div>
		</Panel>
	);
};

LoginPanel.propTypes = {
	onLoginSuccess: PropTypes.func.isRequired
};

export default LoginPanel;
