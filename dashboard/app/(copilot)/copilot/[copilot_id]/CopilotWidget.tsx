import "@openchatai/copilot-widget/index.css";
import {
    CopilotWidget,
    Root
} from '@openchatai/copilot-widget';


export default function Widget() {
    return <Root
        options={{
            apiUrl: "http://localhost:8888/backend/api",
            token: "",
            initialMessage: "Hey Pal!",
            headers: {}
        }}
    >
        <div className="[&>div]:static [&>div]:!max-h-full [&>div]:!h-full h-full overflow-hidden border-border border rounded-lg">
            <CopilotWidget
                triggerSelector="#triggerSelector"
            />
        </div>
    </Root>
}