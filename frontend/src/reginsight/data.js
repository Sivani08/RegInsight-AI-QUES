import {useEffect, useState} from 'react';
import {cachedRequest} from './request-cache.js';

export async function request(path, body, signal) {
  return cachedRequest(path,body,signal);
}

export function useResource(path, version = 0) {
  const [state, setState] = useState({path:null,data: null, error: '', loading: true});
  useEffect(() => {
    const controller = new AbortController();
    setState(old=>({path,data:old.path===path?old.data:null,error:'',loading:Boolean(path)}));
    if (path) cachedRequest(path, null, controller.signal, Boolean(version))
      .then(data => {if(!controller.signal.aborted)setState({path,data, error: '', loading: false});})
      .catch(error => { if (!controller.signal.aborted) setState({path,data: null, error: error.message, loading: false}); });
    return () => controller.abort();
  }, [path, version]);
  return state.path===path ? state : {data:null,error:'',loading:Boolean(path)};
}

export const number = value => value == null ? 'Unavailable' : Number(value).toLocaleString('en-US');
export const shortNumber = value => new Intl.NumberFormat('en-US', {notation: 'compact', maximumFractionDigits: 1}).format(value);
export const dateTime = value => value ? new Date(value).toLocaleString('en-GB', {dateStyle: 'medium', timeStyle: 'short'}) : 'Not supplied';
export const queryString = values => new URLSearchParams(Object.entries(values).filter(([,v]) => v !== '' && v != null)).toString();

export function riskLabel(value) { return String(value || 'Unclassified').toLowerCase().replaceAll(' ', '-'); }
