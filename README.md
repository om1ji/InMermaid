# InMermaid Bot

A Telegram bot for rendering Mermaid diagrams in inline mode. Similar to [InLaTeXbot](https://github.com/vdrhtc/InLaTeXbot) but for Mermaid diagrams.

![image](https://github.com/user-attachments/assets/939d0907-0e07-441e-a9c1-58a119d080f5)


## How It Works

### Inline Mode
1. Type `@inmermaidbot` followed by your Mermaid diagram code in any chat
2. The bot validates the syntax and shows the result
3. Select the result to share the diagram code
4. For the actual image, send the code to the bot in direct messages

### Direct Messages
1. Start a chat with the bot
2. Send your Mermaid diagram code
3. Receive a PNG image

## Installation

### Prerequisites

- Python 3.8+
- Telegram Bot Token (get from [@BotFather](https://t.me/botfather))

### Local Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/inmermaid-bot.git
   cd inmermaid-bot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright browser**
   ```bash
   python -m playwright install chromium
   ```

4. **Set up environment variables**
   
   Create a `.env` file:
   ```bash
   BOT_TOKEN=your_telegram_bot_token_here
   ```

5. **Run the bot**
   ```bash
   python bot.py
   ```

### Docker Setup

1. **Build the image**
   ```bash
   docker build -t inmermaid-bot .
   ```

2. **Run the container**
   ```bash
   docker run -e BOT_TOKEN=your_token_here inmermaid-bot
   ```


## Supported Diagram Types

- **Flowchart** - Flow diagrams and flowcharts
- **Sequence Diagram** - Sequence diagrams for interactions
- **Class Diagram** - UML class diagrams
- **State Diagram** - State transition diagrams
- **Entity Relationship Diagram** - Database ER diagrams
- **User Journey** - User journey maps
- **Gantt Chart** - Project timeline charts
- **Pie Chart** - Pie and donut charts
- **Quadrant Chart** - Four-quadrant analysis
- **Timeline** - Timeline diagrams
- **Mindmap** - Mind mapping diagrams
- And many more!

## Example Diagrams

### Flowchart
```
graph TD
    A[Start] --> B{Decision}
    B -->|Yes| C[Action 1]
    B -->|No| D[Action 2]
    C --> E[End]
    D --> E
```

### Sequence Diagram
```
sequenceDiagram
    participant Alice
    participant Bob
    Alice->>Bob: Hello Bob!
    Bob-->>Alice: Hello Alice!
    Alice->>Bob: How are you?
    Bob-->>Alice: I'm good, thanks!
```

### Class Diagram
```
classDiagram
    Animal <|-- Duck
    Animal <|-- Fish
    Animal : +int age
    Animal : +String gender
    Animal: +isMammal()
    class Duck{
        +String beakColor
        +swim()
        +quack()
    }
```
