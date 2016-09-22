package edu.cmu.cs.privacy_mediator;

import android.preference.PreferenceActivity;
import android.preference.PreferenceFragment;
import android.os.Bundle;

public class SettingActivity extends PreferenceActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getFragmentManager().beginTransaction().replace(android.R.id.content,
                new MyPreferenceFragment()).commit();
    }

    public static class MyPreferenceFragment extends PreferenceFragment
    {
        @Override
        public void onCreate(final Bundle savedInstanceState)
        {
            super.onCreate(savedInstanceState);
            addPreferencesFromResource(R.xml.cloudletdemo_preferences);
        }
    }

}
