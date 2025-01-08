"""A small progress indicator for long audits, written to stderr."""
import sys


class Progress:
    def __init__(self, label, stream=None, every=10, enabled=True):
        self.label = label
        self.stream = stream if stream is not None else sys.stderr
        self.every = every
        self.enabled = enabled
        self.done = 0

    def tick(self):
        self.done += 1
        if self.enabled and self.done % self.every == 0:
            self.stream.write("{}: {} checked\n".format(self.label, self.done))

    def finish(self):
        if self.enabled and self.done % self.every:
            self.stream.write("{}: {} checked\n".format(self.label, self.done))
