package com.example.birdcheckup;

import android.graphics.Color;
import android.os.Bundle;
import android.view.Gravity;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import java.util.ArrayList;
import java.util.List;

public class MainActivity extends android.app.Activity {
    private LinearLayout root;
    private TextView scoreView;
    private final List<CheckBox> goodChecks = new ArrayList<>();
    private final List<CheckBox> redFlagChecks = new ArrayList<>();

    private int dp(float value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        ScrollView scroll = new ScrollView(this);
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(18), dp(18), dp(18), dp(28));
        scroll.addView(root);
        setContentView(scroll);
        buildUi();
    }

    private TextView title(String text, float size) {
        TextView tv = new TextView(this);
        tv.setText(text);
        tv.setTextSize(size);
        tv.setTextColor(Color.rgb(30, 30, 30));
        tv.setPadding(0, dp(8), 0, dp(8));
        return tv;
    }

    private void addSection(String heading, String explanation) {
        TextView h = title(heading, 21);
        h.setTextColor(Color.rgb(27, 94, 32));
        h.setPadding(0, dp(18), 0, dp(4));
        root.addView(h);
        if (explanation != null && !explanation.isEmpty()) {
            TextView e = title(explanation, 14);
            e.setTextColor(Color.DKGRAY);
            root.addView(e);
        }
    }

    private CheckBox addGood(String text, String note) {
        CheckBox cb = new CheckBox(this);
        cb.setText(text + (note == null ? "" : "\n  " + note));
        cb.setTextSize(16);
        cb.setPadding(0, dp(7), 0, dp(7));
        cb.setOnCheckedChangeListener((buttonView, isChecked) -> updateScore());
        goodChecks.add(cb);
        root.addView(cb);
        return cb;
    }

    private CheckBox addFlag(String text) {
        CheckBox cb = new CheckBox(this);
        cb.setText(text);
        cb.setTextSize(16);
        cb.setPadding(0, dp(7), 0, dp(7));
        cb.setOnCheckedChangeListener((buttonView, isChecked) -> updateScore());
        redFlagChecks.add(cb);
        root.addView(cb);
        return cb;
    }

    private void addSellerQuestion(String q) {
        TextView tv = new TextView(this);
        tv.setText("☐  " + q);
        tv.setTextSize(16);
        tv.setTextColor(Color.rgb(50, 50, 50));
        tv.setPadding(0, dp(8), 0, dp(8));
        root.addView(tv);
    }

    private void buildUi() {
        TextView appTitle = title("🐦 Bird Checkup", 30);
        appTitle.setGravity(Gravity.CENTER);
        appTitle.setTextColor(Color.rgb(27, 94, 32));
        root.addView(appTitle);

        TextView intro = title(
                "A before-you-buy checklist for birds. Health and temperament come before color.",
                15);
        intro.setGravity(Gravity.CENTER);
        root.addView(intro);

        scoreView = title("Good checks: 0 | Red flags: 0\nRisk: INCOMPLETE", 17);
        scoreView.setGravity(Gravity.CENTER);
        scoreView.setPadding(0, dp(12), 0, dp(12));
        root.addView(scoreView);

        addSection("1. Eyes", "A healthy-looking bird should have clear, bright eyes.");
        addGood("Both eyes open normally", null);
        addGood("Eyes look clear and bright", null);
        addGood("No swelling, redness, crust or discharge", null);
        addGood("Not constantly squinting", null);

        addSection("2. Nostrils & face", "Check before handling the bird.");
        addGood("Both nostrils look open", null);
        addGood("Nostrils are clean and dry", null);
        addGood("No mucus or crust around the nostrils", null);

        addSection("3. Breathing",
                "Watch while the bird is calm. Do not judge breathing immediately after chasing or handling.");
        addGood("Beak stays closed while resting", null);
        addGood("Breathing is quiet and effortless", null);
        addGood("No persistent tail bobbing while resting", null);
        addGood("No clicking or wheezing", null);
        addGood("No obvious struggle to breathe", null);

        addSection("4. Feathers",
                "Molting can cause pin feathers; look for overall condition rather than perfection.");
        addGood("Feathers are reasonably clean and groomed", null);
        addGood("No large unexplained bald patches", null);
        addGood("No blood, severe matting or heavy droppings on feathers", null);
        addGood("No obvious signs of constant feather plucking", null);

        addSection("5. Body condition",
                "The exact weight varies by individual; body condition matters more than one number.");
        addGood("Standing upright with a normal posture", null);
        addGood("Body does not look extremely thin or extremely overweight", null);
        addGood("Breastbone is not extremely sharp/prominent", null);
        addGood("No obvious lumps or swelling", null);

        addSection("6. Feet & legs", "Watch the bird perch and move around.");
        addGood("Both feet work normally", null);
        addGood("Grip on the perch looks strong", null);
        addGood("No major swelling, wounds or bleeding", null);
        addGood("No severe crusting or obvious deformity", null);
        addGood("Moves between perches without repeated falling", null);

        addSection("7. Wings & movement", "Do not force the bird to fly just for a test.");
        addGood("No obviously drooping or injured wing", null);
        addGood("Climbs and moves around the cage normally", null);
        addGood("Uses both sides of the body normally", null);

        addSection("8. Droppings",
                "One unusual dropping is not automatically illness; repeated abnormalities matter more.");
        addGood("Several droppings look reasonably consistent", null);
        addGood("Droppings are not repeatedly just liquid", null);
        addGood("No obvious blood or very unusual tarry appearance", null);

        addSection("9. Food & water", "Watch actual behavior, not just what the seller says.");
        addGood("Bird shows normal interest in food", null);
        addGood("Can pick up and swallow food normally", null);
        addGood("Fresh drinking water is actually available", null);
        addGood("Seller can explain the bird's normal daily diet", null);

        addSection("10. Alertness & behavior",
                "A healthy-looking cockatiel should generally be aware of its surroundings.");
        addGood("Looks around and responds to movement/sounds", null);
        addGood("Not constantly fluffed up and sleepy during daytime", null);
        addGood("Not sitting on the cage floor without a clear reason", null);
        addGood("Climbs/perches normally", null);

        addSection("11. Human interaction / possible abuse",
                "Nervousness with a stranger can be normal. Look for the overall pattern.");
        addGood("Approaches or tolerates a hand without extreme panic", null);
        addGood("Can calm down after a new person approaches", null);
        addGood("Seller demonstrates step-up or handling without chasing", null);
        addGood("No obvious old injuries from rough handling", null);

        addSection("12. Shop environment",
                "The surrounding birds and cleanliness can tell you a lot.");
        addGood("Food and water are available and reasonably clean", null);
        addGood("Cages are reasonably clean", null);
        addGood("No severe overcrowding", null);
        addGood("Birds are not being handled roughly", null);
        addGood("No obvious sick or dead birds nearby", null);

        addSection("13. Questions for the seller",
                "Ask these before paying, especially when there is no refund.");
        String[] questions = {
                "How old is he?",
                "When did you get him?",
                "Was he hand-fed?",
                "Was he hand-tamed / regularly handled?",
                "What does he eat every day?",
                "Does he eat pellets, seeds, vegetables or other foods?",
                "Does he drink normally?",
                "Has he ever been sick?",
                "Has he ever had breathing problems?",
                "Has he ever had abnormal droppings?",
                "Has he ever been injured?",
                "Has he ever plucked feathers?",
                "Has he been housed with other birds?",
                "How was the sex confirmed?",
                "Can I watch him eat and drink?",
                "Can I see several droppings?"
        };
        for (String q : questions) addSellerQuestion(q);

        addSection("14. Red flags",
                "Tick any red flag you actually observe. One serious respiratory red flag is enough to stop and reconsider.");
        addFlag("Open-mouth breathing while resting");
        addFlag("Persistent tail bobbing while resting");
        addFlag("Wheezing/clicking/noisy breathing");
        addFlag("Severe lethargy or long periods with closed eyes");
        addFlag("Sitting on cage floor because of weakness");
        addFlag("Eye/nose discharge or major swelling");
        addFlag("Repeated falling or inability to grip");
        addFlag("Obvious serious injury");
        addFlag("Repeatedly abnormal watery/bloody/tarry droppings");
        addFlag("Multiple visibly sick birds in the same shop");
        addFlag("Seller refuses basic health questions");
        addFlag("Seller pressures me to buy immediately");
        addFlag("Seller says obvious breathing difficulty is 'normal'");

        addSection("15. Final decision",
                "Healthy + well-socialized + trustworthy source comes before color or mutation.");

        Button evaluate = new Button(this);
        evaluate.setText("CHECK MY RESULT");
        evaluate.setOnClickListener(v -> showResult());
        root.addView(evaluate);

        Button reset = new Button(this);
        reset.setText("RESET CHECKLIST");
        reset.setOnClickListener(v -> resetChecklist());
        root.addView(reset);

        TextView note = title(
                "Important: this app is a screening checklist, not a veterinary diagnosis. Birds can hide illness. If a seller allows it, a pre-purchase avian-vet exam is the safest option.",
                14);
        note.setTextColor(Color.DKGRAY);
        note.setPadding(0, dp(14), 0, 0);
        root.addView(note);

        updateScore();
    }

    private void updateScore() {
        int checked = 0;
        for (CheckBox cb : goodChecks) if (cb.isChecked()) checked++;
        int flags = 0;
        for (CheckBox cb : redFlagChecks) if (cb.isChecked()) flags++;

        String risk;
        if (flags > 0) {
            risk = flags >= 3 ? "HIGH — STOP / AVOID" : "CAUTION — INVESTIGATE";
        } else if (checked >= 35) {
            risk = "LOWER — STRONG CANDIDATE";
        } else if (checked >= 24) {
            risk = "MEDIUM — INVESTIGATE";
        } else {
            risk = "INCOMPLETE";
        }

        scoreView.setText(
                "Good checks: " + checked + " | Red flags: " + flags + "\nRisk: " + risk);
    }

    private void showResult() {
        int checked = 0;
        for (CheckBox cb : goodChecks) if (cb.isChecked()) checked++;
        int flags = 0;
        for (CheckBox cb : redFlagChecks) if (cb.isChecked()) flags++;

        String message;
        if (flags > 0) {
            message = "AVOID / DO NOT PAY YET\n\nYou marked " + flags
                    + " red flag(s). Resolve the problem or choose another bird.\n\nHealth comes before mutation/color.";
        } else if (checked >= 35) {
            message = "BUY CANDIDATE ✅\n\nNo red flags marked and most checks are reassuring. Still use a vet exam whenever the seller permits one.";
        } else {
            message = "INVESTIGATE FURTHER ⚠️\n\nYou have not collected enough reassuring evidence yet. Ask the seller more questions and keep watching the bird.";
        }

        new android.app.AlertDialog.Builder(this)
                .setTitle("Bird Checkup Result")
                .setMessage(message)
                .setPositiveButton("OK", null)
                .show();
    }

    private void resetChecklist() {
        for (CheckBox cb : goodChecks) cb.setChecked(false);
        for (CheckBox cb : redFlagChecks) cb.setChecked(false);
        Toast.makeText(this, "Checklist reset", Toast.LENGTH_SHORT).show();
        updateScore();
    }
}
