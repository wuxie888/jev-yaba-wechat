// Keep the signed application alive as the responsible parent of the Python UI.
// A shell script used directly as CFBundleExecutable loses that app identity on exec.
#import <Foundation/Foundation.h>
#include <signal.h>

static volatile sig_atomic_t childPID = 0;
static void forwardSignal(int signalNumber) {
    if (childPID > 0) kill(childPID, signalNumber);
}

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        NSString *script = [[NSBundle mainBundle] pathForResource:@"bootstrap" ofType:@"sh"];
        if (!script) {
            NSLog(@"Missing bootstrap.sh");
            return 1;
        }
        NSTask *task = [[NSTask alloc] init];
        task.executableURL = [NSURL fileURLWithPath:@"/bin/zsh"];
        task.arguments = @[script];
        NSError *error = nil;
        if (![task launchAndReturnError:&error]) {
            NSLog(@"Unable to launch application: %@", error.localizedDescription);
            return 1;
        }
        childPID = task.processIdentifier;
        signal(SIGTERM, forwardSignal);
        signal(SIGINT, forwardSignal);
        [task waitUntilExit];
        childPID = 0;
        return task.terminationStatus;
    }
}
