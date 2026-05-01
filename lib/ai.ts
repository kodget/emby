import axios from "axios";

const options = {
  method: "POST",
  url: "https://gemini-1-5-flash.p.rapidapi.com/",
  headers: {
    "x-rapidapi-key": "e2b9507f2bmsh2ab87b5b1a01727p1890dajsn024e36a56f93",
    "x-rapidapi-host": "gemini-1-5-flash.p.rapidapi.com",
    "Content-Type": "application/json",
  },
  data: {
    model: "gemini-1.5-flash",
    messages: [
      {
        role: "user",
        content:
          "There are ten birds in a tree. A hunter shoots one. How many are left in the tree?",
      },
    ],
  },
};

export async function fetchGemini(prompt: string) {
  try {
    const response = await axios.request({
      ...options,
      data: { ...options.data, messages: [{ role: "user", content: prompt }] },
    });
    return response.data;
  } catch (error) {
    console.error(error);
    throw error;
  }
}
