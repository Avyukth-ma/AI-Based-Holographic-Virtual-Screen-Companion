import { useState, useCallback, useRef } from 'react';

export function usePushToTalk() {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const recognitionRef = useRef(null);
  const isListeningRef = useRef(false);

  const initRecognition = useCallback(() => {
    if (recognitionRef.current) return recognitionRef.current;
    
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.warn("Speech Recognition API is not supported in this browser.");
      return null;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onresult = (event) => {
      let currentTranscript = '';
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
            currentTranscript += event.results[i][0].transcript;
        }
      }
      if (currentTranscript) {
        setTranscript(prev => prev ? prev + ' ' + currentTranscript : currentTranscript);
      }
    };

    recognition.onerror = (event) => {
      console.error("Speech recognition error:", event.error);
      setIsListening(false);
      isListeningRef.current = false;
    };

    recognition.onend = () => {
      if (isListeningRef.current && recognitionRef.current) {
        try {
          recognitionRef.current.start();
        } catch(e) {}
      } else {
        setIsListening(false);
        isListeningRef.current = false;
      }
    };

    recognitionRef.current = recognition;
    return recognition;
  }, []);

  const startListening = useCallback(() => {
    setTranscript('');
    setIsListening(true);
    isListeningRef.current = true;
    const recognition = initRecognition();
    if (recognition) {
      try {
        recognition.start();
      } catch (e) {
        console.warn("Recognition already started");
      }
    }
  }, [initRecognition]);

  const stopListening = useCallback(() => {
    setIsListening(false);
    isListeningRef.current = false;
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
  }, []);

  return { isListening, transcript, startListening, stopListening, setTranscript };
}
